"""
State machine для переходов статусов заказа.

Два графа переходов — для stock и made_to_order товаров. Разница
в наличии стадий in_production/produced для made_to_order.

Чистая функция без побочных эффектов — проверка «разрешён ли
переход из А в Б». Используется в OrderStatusService.change_status
и в валидирующем сигнале pre_save.
"""

from apps.orders.models import OrderStatus

STOCK_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.PENDING_PAYMENT: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.ASSEMBLING, OrderStatus.CANCELLED},
    OrderStatus.ASSEMBLING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.IN_DELIVERY},
    OrderStatus.IN_DELIVERY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}

MADE_TO_ORDER_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.PENDING_PAYMENT: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.IN_PRODUCTION, OrderStatus.CANCELLED},
    OrderStatus.IN_PRODUCTION: {OrderStatus.PRODUCED, OrderStatus.CANCELLED},
    OrderStatus.PRODUCED: {OrderStatus.ASSEMBLING},
    OrderStatus.ASSEMBLING: {OrderStatus.SHIPPED},
    OrderStatus.SHIPPED: {OrderStatus.IN_DELIVERY},
    OrderStatus.IN_DELIVERY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def _get_graph(product_type: str) -> dict[str, set[str]]:
    """Выбрать граф переходов по типу товара."""
    if product_type == "made_to_order":
        return MADE_TO_ORDER_TRANSITIONS
    return STOCK_TRANSITIONS


def is_transition_allowed(current: str, target: str, product_type: str = "stock") -> bool:
    """Разрешён ли переход current → target для данного типа товара."""
    graph = _get_graph(product_type)
    allowed = graph.get(current, set())
    return target in allowed


def get_allowed_transitions(current: str, product_type: str = "stock") -> set[str]:
    """Множество разрешённых следующих статусов (полезно для UI)."""
    graph = _get_graph(product_type)
    return graph.get(current, set())
