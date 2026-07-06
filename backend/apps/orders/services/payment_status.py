"""
Сервис управления статусом оплаты заказа.

Ось оплаты независима от физического статуса товара (см. OrderStatusService).
change_payment_status:
- валидирует переход через is_payment_transition_allowed
- обновляет payment_status
- при переходе в paid ставит paid_at
- создаёт запись PaymentStatusHistory
- всё под @transaction.atomic
"""

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import ValidationError
from apps.orders.models import Order, PaymentStatus, PaymentStatusHistory
from apps.orders.services.payment_transitions import is_payment_transition_allowed

if TYPE_CHECKING:
    from apps.users.models import User


class PaymentStatusService:
    """Сервис смены статуса оплаты."""

    @staticmethod
    @transaction.atomic
    def change_payment_status(
        order: Order,
        new_status: str,
        changed_by: "User | None" = None,
        comment: str = "",
    ) -> Order:
        """
        Сменить статус оплаты с валидацией и побочными эффектами.

        Args:
            order: заказ
            new_status: целевой статус из PaymentStatus
            changed_by: кто меняет (None для автоматических — например webhook)
            comment: комментарий к записи истории

        Returns:
            Обновлённый Order

        Raises:
            ValidationError("invalid_payment_transition"): переход запрещён.
        """
        old_status = order.payment_status

        if not is_payment_transition_allowed(old_status, new_status):
            raise ValidationError(
                error_code="invalid_payment_transition",
                message=f"Недопустимый переход оплаты: {old_status} → {new_status}.",
            )

        order.payment_status = new_status
        if new_status == PaymentStatus.PAID:
            order.paid_at = timezone.now()

        order.save(update_fields=["payment_status", "paid_at", "updated_at"])

        PaymentStatusHistory.objects.create(
            order=order,
            status_from=old_status,
            status_to=new_status,
            changed_by=changed_by,
            comment=comment,
            is_automatic=(changed_by is None),
        )

        return order
