"""
State machine для переходов статусов заказа (физический цикл товара).

Два графа — для stock и made_to_order. Оплата НЕ входит в этот граф:
она отдельная ось (PaymentStatus). Здесь только физика: где товар.

stock:         created → assembling → shipped → in_delivery → delivered
made_to_order: created → in_production → produced → assembling →
                shipped → in_delivery → delivered
cancelled — до shipped (stock) или до in_production (made_to_order).

Чистые функции без побочных эффектов. Используются в
OrderStatusService.change_status и в валидации Order.save().
"""

from apps.orders.models import OrderStatus

STOCK_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.CREATED: {OrderStatus.ASSEMBLING, OrderStatus.CANCELLED},
    OrderStatus.ASSEMBLING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.IN_DELIVERY},
    OrderStatus.IN_DELIVERY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}

MADE_TO_ORDER_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.CREATED: {OrderStatus.IN_PRODUCTION, OrderStatus.CANCELLED},
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
