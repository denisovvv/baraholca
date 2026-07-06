"""
State machine для переходов статусов оплаты (ось PaymentStatus).

Отдельно от физического цикла товара (status). Здесь только деньги:
получена ли оплата, не прошла, возвращена.

pending → paid     (оплата прошла)
pending → failed   (оплата не прошла)
failed  → paid     (повторная попытка успешна)
failed  → pending  (сброс на новую попытку)
paid    → refunded (возврат)
refunded — терминал.

Чистые функции без побочных эффектов. Используются в
PaymentStatusService.change_payment_status.
"""

from apps.orders.models import PaymentStatus

PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    PaymentStatus.PENDING: {PaymentStatus.PAID, PaymentStatus.FAILED},
    PaymentStatus.FAILED: {PaymentStatus.PAID, PaymentStatus.PENDING},
    PaymentStatus.PAID: {PaymentStatus.REFUNDED},
    PaymentStatus.REFUNDED: set(),
}


def is_payment_transition_allowed(current: str, target: str) -> bool:
    """Разрешён ли переход payment_status current → target."""
    return target in PAYMENT_TRANSITIONS.get(current, set())


def get_allowed_payment_transitions(current: str) -> set[str]:
    """Множество разрешённых следующих статусов оплаты (для UI)."""
    return PAYMENT_TRANSITIONS.get(current, set())
