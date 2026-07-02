"""
Распределение товаров одного продавца по его складам.

WarehouseAllocator — чистая функция распределения без побочных эффектов.
Не пишет в БД: не создаёт Order, не резервирует ProductStock. Только
читает Warehouse и ProductStock, возвращает AllocationResult или бросает
исключение.

Разделение на аллокатор и CheckoutService: аллокатор решает "что откуда
брать", CheckoutService (шаг 6b) использует результат для транзакционного
создания заказов. Разделение упрощает тестирование — распределение
проверяется без транзакций и записей в БД.

Два метода на разные случаи delivery_method (по решению Q25):
- allocate_for_courier: гибрид алгоритм с delivery_area и расстоянием
- allocate_for_pickup: всё-или-ничего в переданном складе

Аллокатор доверяет что товары уже проверены на is_active/
is_available_for_sale (по решению Q26 — эта проверка делается в
CheckoutService перед вызовом аллокатора).
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from apps.catalog.models import ProductStock, Warehouse
from apps.common.exceptions import NotFoundError, ValidationError
from apps.orders.services.allocation import (
    AllocatedItem,
    AllocationResult,
    NoDeliveryAvailableError,
    PickupNotAvailableError,
    WarehouseAllocation,
)

if TYPE_CHECKING:
    from apps.catalog.models import Product
    from apps.sellers.models import Seller


class WarehouseAllocator:
    """
    Статические методы распределения товаров по складам продавца.

    Класс, а не модуль с функциями, чтобы:
    - логически сгруппировать связанные методы
    - в будущем можно было заменить статические методы на инстанс-методы
      (например, если появится DI-контейнер или общая конфигурация)
    """

    @staticmethod
    def allocate_for_courier(
        seller: "Seller",
        items: list[tuple["Product", int]],
        delivery_point: Point,
    ) -> AllocationResult:
        """
        Распределить товары одного продавца по складам для доставки курьером.

        Правила (по решениям Q18, Q22, Q20):
        1. Учитываются только is_active=True склады, чья delivery_area
           содержит точку клиента.
        2. Если ни один склад не покрывает адрес — NoDeliveryAvailableError.
        3. Если один склад может отгрузить все товары — берём ближайший
           из таких. Одна отправка.
        4. Если нет — жадный алгоритм минимизации: сортируем склады
           по покрытию (сколько товаров могут дать) убыв., при равенстве —
           по расстоянию возр. Распределяем по этому порядку.
        5. Если после всех складов есть недораспределённое — 422
           not_enough_stock с details по каждому товару.

        Args:
            seller: продавец
            items: список (product, requested_quantity)
            delivery_point: координаты адреса клиента (SRID 4326)

        Returns:
            AllocationResult с одной или несколькими WarehouseAllocation

        Raises:
            NoDeliveryAvailableError: ни один склад продавца не доставляет
                по адресу.
            ValidationError("not_enough_stock"): товары не покрываются
                суммой всех подходящих складов.
        """
        # Шаг 1: активные склады продавца, покрывающие адрес.
        # Аннотируем расстояние для сортировки.
        warehouses = list(
            Warehouse.objects.filter(
                seller=seller,
                is_active=True,
                delivery_area__contains=delivery_point,
            )
            .annotate(distance=Distance("location", delivery_point))
            .order_by("distance")
        )

        if not warehouses:
            raise NoDeliveryAvailableError()

        # Шаг 2: построить матрицу "склад x товар → available".
        # available = quantity - reserved_quantity.
        # Отсутствие ProductStock записи трактуется как available=0.
        stock_matrix = WarehouseAllocator._build_stock_matrix(warehouses, items)

        # Шаг 3: попробовать одну отправку — найти ближайший склад,
        # покрывающий все товары.
        single_warehouse = WarehouseAllocator._find_single_warehouse(
            warehouses, items, stock_matrix
        )
        if single_warehouse is not None:
            return AllocationResult(
                allocations=[
                    WarehouseAllocation(
                        warehouse=single_warehouse,
                        items=[
                            AllocatedItem(product=product, quantity=qty) for product, qty in items
                        ],
                    )
                ]
            )

        # Шаг 4: жадное распределение по нескольким складам.
        allocations, unmet = WarehouseAllocator._greedy_allocate(warehouses, items, stock_matrix)

        if unmet:
            # Есть товары которые не покрыты суммой складов.
            raise ValidationError(
                error_code="not_enough_stock",
                message="Недостаточно товаров на складе.",
                details=WarehouseAllocator._build_stock_details(unmet, items),
            )

        return AllocationResult(allocations=allocations)

    @staticmethod
    def allocate_for_pickup(
        seller: "Seller",
        items: list[tuple["Product", int]],
        warehouse_uuid: UUID,
    ) -> AllocationResult:
        """
        Распределить товары одного продавца по одному складу самовывоза.

        Правила (по решениям Q19, Q23):
        1. Склад ищется по (uuid, seller, is_active=True).
        2. Если не найден — 404 warehouse_not_found.
        3. Если pickup_available=False — PickupNotAvailableError.
        4. Все товары должны помещаться в этот склад.
        5. Если хоть один товар не помещается — 422 not_enough_stock
           с details.

        Args:
            seller: продавец (для проверки принадлежности склада)
            items: список (product, requested_quantity)
            warehouse_uuid: UUID склада самовывоза (передал клиент)

        Returns:
            AllocationResult с ровно одной WarehouseAllocation

        Raises:
            NotFoundError("warehouse_not_found"): склад не найден или
                не принадлежит продавцу или неактивен.
            PickupNotAvailableError: pickup_available=False.
            ValidationError("not_enough_stock"): хоть один товар не
                помещается в этот склад.
        """
        # Шаг 1: найти склад по uuid, принадлежащий продавцу.
        # uuid_1c у нас в модели unique + nullable, но мы используем
        # его как публичный идентификатор склада (uuid из 1С).
        try:
            warehouse = Warehouse.objects.get(
                uuid_1c=warehouse_uuid,
                seller=seller,
                is_active=True,
            )
        except Warehouse.DoesNotExist as exc:
            raise NotFoundError(
                error_code="warehouse_not_found",
                message="Склад не найден или недоступен.",
            ) from exc

        # Шаг 2: проверить pickup_available.
        if not warehouse.pickup_available:
            raise PickupNotAvailableError()

        # Шаг 3: проверить остатки на этом складе для всех товаров.
        stock_matrix = WarehouseAllocator._build_stock_matrix([warehouse], items)

        unmet: dict[int, int] = {}
        allocated_items: list[AllocatedItem] = []
        for product, requested in items:
            available = stock_matrix.get(warehouse.pk, {}).get(product.pk, 0)
            if available < requested:
                # Не хватает — запомним для details.
                unmet[product.pk] = available
            else:
                allocated_items.append(AllocatedItem(product=product, quantity=requested))

        if unmet:
            raise ValidationError(
                error_code="not_enough_stock",
                message="Недостаточно товаров на выбранном складе.",
                details=WarehouseAllocator._build_stock_details(unmet, items),
            )

        return AllocationResult(
            allocations=[WarehouseAllocation(warehouse=warehouse, items=allocated_items)]
        )

    # -------------------------------------------------------------------
    # Внутренние методы построения матрицы и алгоритма
    # -------------------------------------------------------------------

    @staticmethod
    def _build_stock_matrix(
        warehouses: Sequence[Warehouse],
        items: list[tuple["Product", int]],
    ) -> dict[int, dict[int, int]]:
        """
        Построить матрицу {warehouse_pk: {product_pk: available}}.

        available = ProductStock.quantity - ProductStock.reserved_quantity,
        не меньше 0. Отсутствие записи ProductStock трактуется как 0.

        Один SQL-запрос через IN warehouse_id и IN product_id вместо
        NxM запросов — критично для производительности.
        """
        warehouse_pks = [w.pk for w in warehouses]
        product_pks = [p.pk for p, _ in items]

        matrix: dict[int, dict[int, int]] = {pk: {} for pk in warehouse_pks}

        stocks = ProductStock.objects.filter(
            warehouse_id__in=warehouse_pks,
            product_id__in=product_pks,
        )
        for stock in stocks:
            available = max(0, stock.quantity - stock.reserved_quantity)
            matrix[stock.warehouse_id][stock.product_id] = available

        return matrix

    @staticmethod
    def _find_single_warehouse(
        warehouses: Sequence[Warehouse],
        items: list[tuple["Product", int]],
        stock_matrix: dict[int, dict[int, int]],
    ) -> Warehouse | None:
        """
        Найти ближайший склад, который покрывает все товары.

        warehouses уже отсортированы по расстоянию (ascending).
        Возвращает первый подходящий или None.
        """
        for warehouse in warehouses:
            stocks_here = stock_matrix.get(warehouse.pk, {})
            covers_all = all(
                stocks_here.get(product.pk, 0) >= requested for product, requested in items
            )
            if covers_all:
                return warehouse
        return None

    @staticmethod
    def _greedy_allocate(
        warehouses: Sequence[Warehouse],
        items: list[tuple["Product", int]],
        stock_matrix: dict[int, dict[int, int]],
    ) -> tuple[list[WarehouseAllocation], dict[int, int]]:
        """
        Жадный алгоритм минимизации количества отправлений.

        Стратегия: на каждом шаге выбирать склад, который покрывает
        максимальное число из ещё нераспределённых товаров. При равенстве
        покрытия — выбирать ближайший к клиенту (warehouses уже отсортированы
        по расстоянию, поэтому first-wins даёт правильный порядок).

        Returns:
            (allocations, unmet_by_product)
            unmet_by_product — {product_pk: недостающее_количество}
        """
        # Копия остатков товаров, будем уменьшать по мере распределения.
        remaining: dict[int, int] = {p.pk: qty for p, qty in items}
        # Мапа pk → Product для восстановления объекта в конце.
        product_by_pk: dict[int, Product] = {p.pk: p for p, _ in items}

        allocations: list[WarehouseAllocation] = []

        # Копия матрицы, будем уменьшать доступное на распределённое.
        available: dict[int, dict[int, int]] = {
            wh_pk: dict(products) for wh_pk, products in stock_matrix.items()
        }

        while any(qty > 0 for qty in remaining.values()):
            # Найти склад с максимальным покрытием оставшихся товаров.
            best_warehouse = None
            best_coverage = 0

            for warehouse in warehouses:
                coverage = sum(
                    min(available.get(warehouse.pk, {}).get(pk, 0), qty)
                    for pk, qty in remaining.items()
                    if qty > 0
                )
                # Строго больше — не >=. warehouses отсортированы,
                # поэтому первый склад с макс. покрытием — ближайший.
                if coverage > best_coverage:
                    best_coverage = coverage
                    best_warehouse = warehouse

            if best_warehouse is None or best_coverage == 0:
                # Ни один склад не может дать ничего из оставшегося.
                break

            # Забрать из best_warehouse что можно.
            allocated_items: list[AllocatedItem] = []
            for pk, qty in list(remaining.items()):
                if qty == 0:
                    continue
                can_take = min(available[best_warehouse.pk].get(pk, 0), qty)
                if can_take > 0:
                    allocated_items.append(
                        AllocatedItem(product=product_by_pk[pk], quantity=can_take)
                    )
                    remaining[pk] -= can_take
                    available[best_warehouse.pk][pk] -= can_take

            if allocated_items:
                allocations.append(
                    WarehouseAllocation(warehouse=best_warehouse, items=allocated_items)
                )

        # Что осталось нераспределённым
        unmet = {pk: qty for pk, qty in remaining.items() if qty > 0}
        return allocations, unmet

    @staticmethod
    def _build_stock_details(
        unmet_by_pk: dict[int, int],
        items: list[tuple["Product", int]],
    ) -> list[dict]:
        """
        Сформировать details для ошибки not_enough_stock.

        Формат по решению Q27:
            [{"product_id": 42, "product_name": "Кружка",
              "requested": 5, "available": 3}, ...]

        available = requested - unmet_qty (сколько всё же удалось найти
        суммарно по складам). Для pickup unmet_qty содержит просто
        available значение (см. использование).
        """
        # Мапа pk → (product, requested)
        by_pk = {p.pk: (p, qty) for p, qty in items}

        details = []
        for pk, unmet_qty in unmet_by_pk.items():
            if pk not in by_pk:
                continue
            product, requested = by_pk[pk]
            # Для courier unmet_qty — недостающее, значит available = requested - unmet
            # Для pickup unmet_qty — сколько есть (сколько не хватает не важно)
            # Для унификации: available = requested - unmet, но не меньше 0
            available = max(0, requested - unmet_qty)
            details.append(
                {
                    "product_id": product.pk,
                    "product_name": product.name_short,
                    "requested": requested,
                    "available": available,
                }
            )
        return details
