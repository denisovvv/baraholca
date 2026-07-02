"""
Структуры результата и специфичные исключения аллокатора складов.

WarehouseAllocator (в отдельном модуле) распределяет позиции корзины
по складам продавца согласно правилам:
- courier: гибрид (одна отправка если помещается; иначе минимум отправлений)
- pickup: всё или ничего в переданном складе

Итог — AllocationResult со списком групп WarehouseAllocation. Каждая группа
приведёт к одному Order в CheckoutService. Разделение "распределить" и
"создать заказы" позволяет тестировать логику распределения без БД.

Исключения этого модуля отражают специфичные состояния распределения:
NoDeliveryAvailableError — ни один активный склад продавца не покрывает
адрес клиента своей delivery_area (для courier).
PickupNotAvailableError — переданный клиентом склад не принимает самовывоз.

Оба наследуются от ValidationError (422) — специфичные состояния входных
данных, которые нельзя обработать. Общие ошибки (товар не найден,
недостаточно остатков) используют существующие NotFoundError и
ValidationError из apps.common.exceptions.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from apps.common.exceptions import ValidationError

if TYPE_CHECKING:
    from apps.catalog.models import Product, Warehouse


@dataclass(frozen=True)
class AllocatedItem:
    """
    Одна позиция в распределении: какой товар, в каком количестве.

    frozen=True делает объект неизменяемым — гарантия что распределение
    после расчёта не изменится случайно в другом месте кода.
    """

    product: "Product"
    quantity: int


@dataclass(frozen=True)
class WarehouseAllocation:
    """
    Группа позиций для одного склада.

    Одна WarehouseAllocation превратится в один Order при создании.
    Список items — что именно этот склад должен отгрузить.

    default_factory=list гарантирует что каждая новая WarehouseAllocation
    имеет свой список — без разделения между экземплярами (частая ловушка
    с mutable defaults в dataclass).
    """

    warehouse: "Warehouse"
    items: list[AllocatedItem] = field(default_factory=list)


@dataclass(frozen=True)
class AllocationResult:
    """
    Результат распределения корзины по складам.

    allocations — список групп, каждая создаст отдельный Order.
    Для простого случая (все товары в одном складе) — одна группа.
    Для сложного (разные склады) — несколько.

    Пустой список allocations означает что корзина пуста или все товары
    отфильтровались — этого не должно случаться в норме, аллокатор
    в таких ситуациях бросает исключение.
    """

    allocations: list[WarehouseAllocation]


class NoDeliveryAvailableError(ValidationError):
    """
    Ни один активный склад продавца не покрывает адрес клиента.

    Бросается только для delivery_method=courier, когда все склады
    продавца (is_active=True) имеют delivery_area, не содержащую
    точку клиента. Для клиента это значит "продавец не доставляет
    по этому адресу" — пусть выбирает pickup или другого продавца.

    Наследуется от ValidationError — маппится на 422.
    """

    default_error_code = "no_delivery_available"
    default_message = "Продавец не осуществляет доставку по указанному адресу."


class PickupNotAvailableError(ValidationError):
    """
    Переданный warehouse_uuid не принимает самовывоз.

    Бросается для delivery_method=pickup, когда склад найден, но
    pickup_available=False. Клиент должен выбрать другой склад
    или переключиться на courier.

    Наследуется от ValidationError — маппится на 422.
    """

    default_error_code = "pickup_not_available"
    default_message = "На выбранном складе самовывоз недоступен."
