"""
Unit-тесты WarehouseAllocator.

Аллокатор — чистая функция распределения без API. Тесты проверяют
все ветви алгоритма изолированно от HTTP-стека:
- courier: гибрид (один склад vs минимум отправлений)
- pickup: всё-или-ничего
- граничные случаи (нет доставки, нет остатков, неактивные склады)

Тестовые данные создаются в setUpTestData один раз для всех тестов
класса. Полигоны delivery_area — квадратные боксы вокруг координат
склада: контроль "покрывает/не покрывает" читается сразу, без карты.
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase

from apps.catalog.models import Category, Product, ProductStock, Warehouse
from apps.common.exceptions import NotFoundError, ValidationError
from apps.orders.services.allocation import (
    NoDeliveryAvailableError,
    PickupNotAvailableError,
)
from apps.orders.services.warehouse_allocator import WarehouseAllocator
from apps.sellers.models import Seller


class WarehouseAllocatorTestCase(TestCase):
    """Тесты WarehouseAllocator для courier и pickup."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.seller = Seller.objects.create(
            name="Тестовый ИП",
            short_name="Тестовый",
            inn="111111111111",
            ogrnip="222222222222222",
            contact_phone="+79990000001",
            order_prefix="TST",
        )

        cls.warehouse_center = cls._create_warehouse(
            "Центральный", lat=52.9, lng=40.5, box_radius=0.1
        )
        cls.warehouse_north = cls._create_warehouse("Северный", lat=52.95, lng=40.5, box_radius=0.1)
        cls.warehouse_south = cls._create_warehouse("Южный", lat=52.85, lng=40.5, box_radius=0.1)
        cls.warehouse_inactive = cls._create_warehouse(
            "Неактивный", lat=52.9, lng=40.5, box_radius=0.1, is_active=False
        )

        cls.category = Category.objects.create(name="Тесты", slug="tests")
        cls.product_mug = cls._create_product("Кружка", cls.category, price="500.00")
        cls.product_shirt = cls._create_product("Футболка", cls.category, price="1000.00")
        cls.product_socks = cls._create_product("Носки", cls.category, price="200.00")

        cls.delivery_point = Point(40.5, 52.9, srid=4326)

    @classmethod
    def _box_around(cls, lat: float, lng: float, radius: float = 0.05) -> Polygon:
        return Polygon(
            (
                (lng - radius, lat - radius),
                (lng + radius, lat - radius),
                (lng + radius, lat + radius),
                (lng - radius, lat + radius),
                (lng - radius, lat - radius),
            ),
            srid=4326,
        )

    @classmethod
    def _create_warehouse(
        cls,
        name: str,
        lat: float,
        lng: float,
        box_radius: float = 0.05,
        pickup_available: bool = True,
        is_active: bool = True,
    ) -> Warehouse:
        return Warehouse.objects.create(
            seller=cls.seller,
            name=name,
            address=f"г.Тестовый, {name}",
            location=Point(lng, lat, srid=4326),
            delivery_area=cls._box_around(lat, lng, box_radius),
            pickup_available=pickup_available,
            is_active=is_active,
            uuid_1c=uuid4(),
        )

    @classmethod
    def _create_product(cls, name: str, category: Category, price: str = "100.00") -> Product:
        return Product.objects.create(
            name_short=name,
            name_full=f"{name} тестовая полная",
            seller=cls.seller,
            category=category,
            base_price=Decimal(price),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def _create_stock(
        self,
        product: Product,
        warehouse: Warehouse,
        quantity: int,
        reserved: int = 0,
    ) -> ProductStock:
        stock, _ = ProductStock.objects.update_or_create(
            product=product,
            warehouse=warehouse,
            defaults={"quantity": quantity, "reserved_quantity": reserved},
        )
        return stock

    # -------------------------------------------------------------------
    # Тесты allocate_for_courier
    # -------------------------------------------------------------------

    def test_courier_single_warehouse_covers_all(self) -> None:
        """
        Все товары помещаются в один склад — одна отправка.
        Центральный склад имеет всё — используем его.
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=10)
        self._create_stock(self.product_shirt, self.warehouse_center, quantity=5)

        result = WarehouseAllocator.allocate_for_courier(
            seller=self.seller,
            items=[(self.product_mug, 2), (self.product_shirt, 1)],
            delivery_point=self.delivery_point,
        )

        self.assertEqual(len(result.allocations), 1)
        self.assertEqual(result.allocations[0].warehouse, self.warehouse_center)
        self.assertEqual(len(result.allocations[0].items), 2)

    def test_courier_closest_of_two_covering_warehouses_wins(self) -> None:
        """
        Оба склада (Центральный и Северный) покрывают все товары.
        Выбираем ближайший — Центральный (расстояние 0 от точки доставки).
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=10)
        self._create_stock(self.product_mug, self.warehouse_north, quantity=10)

        result = WarehouseAllocator.allocate_for_courier(
            seller=self.seller,
            items=[(self.product_mug, 3)],
            delivery_point=self.delivery_point,
        )

        self.assertEqual(len(result.allocations), 1)
        self.assertEqual(result.allocations[0].warehouse, self.warehouse_center)

    def test_courier_splits_into_two_warehouses(self) -> None:
        """
        Товары не помещаются в один склад — разбивается на две отправки.
        Кружка только в Центральном, Футболка только в Северном.
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=5)
        self._create_stock(self.product_shirt, self.warehouse_north, quantity=5)

        result = WarehouseAllocator.allocate_for_courier(
            seller=self.seller,
            items=[(self.product_mug, 2), (self.product_shirt, 1)],
            delivery_point=self.delivery_point,
        )

        self.assertEqual(len(result.allocations), 2)
        warehouses_used = {a.warehouse.name for a in result.allocations}
        self.assertEqual(warehouses_used, {"Центральный", "Северный"})

    def test_courier_no_delivery_available(self) -> None:
        """
        Точка доставки за пределами всех delivery_area.
        Клиент указал далёкий адрес — ни один склад не покрывает.
        """
        far_point = Point(50.0, 40.0, srid=4326)  # далеко от всех складов

        with self.assertRaises(NoDeliveryAvailableError):
            WarehouseAllocator.allocate_for_courier(
                seller=self.seller,
                items=[(self.product_mug, 1)],
                delivery_point=far_point,
            )

    def test_courier_not_enough_stock_with_details(self) -> None:
        """
        Товаров не хватает суммарно по всем складам.
        Запросили 10 кружек, есть только 3+2=5.
        Ошибка содержит details с available для каждого товара.
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=3)
        self._create_stock(self.product_mug, self.warehouse_north, quantity=2)

        with self.assertRaises(ValidationError) as ctx:
            WarehouseAllocator.allocate_for_courier(
                seller=self.seller,
                items=[(self.product_mug, 10)],
                delivery_point=self.delivery_point,
            )
        exc = ctx.exception
        self.assertEqual(exc.error_code, "not_enough_stock")
        self.assertIsNotNone(exc.details)
        self.assertEqual(exc.details[0]["product_id"], self.product_mug.pk)
        self.assertEqual(exc.details[0]["requested"], 10)
        self.assertEqual(exc.details[0]["available"], 5)

    def test_courier_product_not_on_any_warehouse(self) -> None:
        """
        Товара нет ни на одном складе — available=0 в details.
        """
        with self.assertRaises(ValidationError) as ctx:
            WarehouseAllocator.allocate_for_courier(
                seller=self.seller,
                items=[(self.product_mug, 5)],
                delivery_point=self.delivery_point,
            )
        exc = ctx.exception
        self.assertEqual(exc.error_code, "not_enough_stock")
        self.assertEqual(exc.details[0]["available"], 0)

    def test_courier_inactive_warehouse_ignored(self) -> None:
        """
        Неактивный склад не участвует в распределении.
        Если товар есть только в неактивном — ошибка not_enough_stock.
        """
        self._create_stock(self.product_mug, self.warehouse_inactive, quantity=10)

        with self.assertRaises(ValidationError) as ctx:
            WarehouseAllocator.allocate_for_courier(
                seller=self.seller,
                items=[(self.product_mug, 1)],
                delivery_point=self.delivery_point,
            )
        exc = ctx.exception
        self.assertEqual(exc.error_code, "not_enough_stock")

    def test_courier_reserved_quantity_reduces_available(self) -> None:
        """
        reserved_quantity уменьшает доступное для новых заказов.
        Всего 10, зарезервировано 8, доступно 2 — просим 5, не хватает.
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=10, reserved=8)

        with self.assertRaises(ValidationError) as ctx:
            WarehouseAllocator.allocate_for_courier(
                seller=self.seller,
                items=[(self.product_mug, 5)],
                delivery_point=self.delivery_point,
            )
        exc = ctx.exception
        self.assertEqual(exc.details[0]["available"], 2)

    def test_courier_prefers_full_coverage_over_closer(self) -> None:
        """
        Гибрид: если один склад покрывает всё — берём его,
        даже если есть ближайший неполный.
        Центральный (ближайший) — только Кружка.
        Северный — Кружка + Футболка (полное покрытие).
        Ожидаем: Северный (одна отправка), не разбивка.
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=5)
        self._create_stock(self.product_mug, self.warehouse_north, quantity=5)
        self._create_stock(self.product_shirt, self.warehouse_north, quantity=5)

        result = WarehouseAllocator.allocate_for_courier(
            seller=self.seller,
            items=[(self.product_mug, 1), (self.product_shirt, 1)],
            delivery_point=self.delivery_point,
        )

        self.assertEqual(len(result.allocations), 1)
        self.assertEqual(result.allocations[0].warehouse, self.warehouse_north)

    def test_courier_equal_coverage_picks_closer(self) -> None:
        """
        Два склада с равным покрытием — выбираем ближайший.
        Центральный (dist=0) и Северный (dist>0) — оба имеют один товар.
        Ожидаем: Центральный.
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=5)
        self._create_stock(self.product_mug, self.warehouse_north, quantity=5)

        result = WarehouseAllocator.allocate_for_courier(
            seller=self.seller,
            items=[(self.product_mug, 1)],
            delivery_point=self.delivery_point,
        )

        self.assertEqual(result.allocations[0].warehouse, self.warehouse_center)

    # -------------------------------------------------------------------
    # Тесты allocate_for_pickup
    # -------------------------------------------------------------------

    def test_pickup_all_items_available(self) -> None:
        """Все товары есть на переданном складе — одна отправка."""
        self._create_stock(self.product_mug, self.warehouse_center, quantity=5)
        self._create_stock(self.product_shirt, self.warehouse_center, quantity=3)

        result = WarehouseAllocator.allocate_for_pickup(
            seller=self.seller,
            items=[(self.product_mug, 2), (self.product_shirt, 1)],
            warehouse_uuid=self.warehouse_center.uuid_1c,
        )

        self.assertEqual(len(result.allocations), 1)
        self.assertEqual(result.allocations[0].warehouse, self.warehouse_center)
        self.assertEqual(len(result.allocations[0].items), 2)

    def test_pickup_warehouse_not_found(self) -> None:
        """UUID склада не существует — 404 warehouse_not_found."""
        with self.assertRaises(NotFoundError) as ctx:
            WarehouseAllocator.allocate_for_pickup(
                seller=self.seller,
                items=[(self.product_mug, 1)],
                warehouse_uuid=uuid4(),
            )
        self.assertEqual(ctx.exception.error_code, "warehouse_not_found")

    def test_pickup_warehouse_of_different_seller(self) -> None:
        """
        Склад существует, но принадлежит другому продавцу — 404.
        Изоляция: чужие склады не должны быть доступны.
        """
        other_seller = Seller.objects.create(
            name="Другой ИП",
            short_name="Другой",
            inn="333333333333",
            ogrnip="444444444444444",
            contact_phone="+79990000002",
            order_prefix="OTR",
        )
        other_warehouse = Warehouse.objects.create(
            seller=other_seller,
            name="Чужой",
            address="Чужой адрес",
            location=Point(40.5, 52.9, srid=4326),
            delivery_area=self._box_around(52.9, 40.5),
            pickup_available=True,
            is_active=True,
            uuid_1c=uuid4(),
        )

        with self.assertRaises(NotFoundError) as ctx:
            WarehouseAllocator.allocate_for_pickup(
                seller=self.seller,
                items=[(self.product_mug, 1)],
                warehouse_uuid=other_warehouse.uuid_1c,
            )
        self.assertEqual(ctx.exception.error_code, "warehouse_not_found")

    def test_pickup_not_available(self) -> None:
        """Склад найден, но pickup_available=False — 422 pickup_not_available."""
        warehouse_no_pickup = self._create_warehouse(
            "Без самовывоза",
            lat=52.9,
            lng=40.5,
            pickup_available=False,
        )

        with self.assertRaises(PickupNotAvailableError):
            WarehouseAllocator.allocate_for_pickup(
                seller=self.seller,
                items=[(self.product_mug, 1)],
                warehouse_uuid=warehouse_no_pickup.uuid_1c,
            )

    def test_pickup_not_enough_stock(self) -> None:
        """
        Хоть один товар не помещается — 422 not_enough_stock.
        Кружки хватает, футболок нет — вся операция отклоняется.
        """
        self._create_stock(self.product_mug, self.warehouse_center, quantity=5)

        with self.assertRaises(ValidationError) as ctx:
            WarehouseAllocator.allocate_for_pickup(
                seller=self.seller,
                items=[(self.product_mug, 1), (self.product_shirt, 1)],
                warehouse_uuid=self.warehouse_center.uuid_1c,
            )
        exc = ctx.exception
        self.assertEqual(exc.error_code, "not_enough_stock")
        # В details только футболка (та что не помещается)
        product_ids = {d["product_id"] for d in exc.details}
        self.assertIn(self.product_shirt.pk, product_ids)

    def test_pickup_product_missing_available_zero(self) -> None:
        """Товара нет вообще на складе — available=0 в details."""
        with self.assertRaises(ValidationError) as ctx:
            WarehouseAllocator.allocate_for_pickup(
                seller=self.seller,
                items=[(self.product_mug, 3)],
                warehouse_uuid=self.warehouse_center.uuid_1c,
            )
        exc = ctx.exception
        self.assertEqual(exc.details[0]["available"], 0)
