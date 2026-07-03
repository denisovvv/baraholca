"""
Сервис управления статусами заказа.

Основной путь смены статуса — через change_status.
Автоматически:
- валидирует переход через is_transition_allowed
- обновляет связанное поле-дату (paid_at, shipped_at и т.д.)
- при отмене освобождает резерв ProductStock
- создаёт запись OrderStatusHistory
- всё под @transaction.atomic

Прямой Order.save() тоже провалидирует переход (защита в модели),
но не обновит даты и не запишет историю. Поэтому смену статуса
всегда делаем через этот сервис.
"""

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import ProductStock
from apps.common.exceptions import ValidationError
from apps.orders.models import Order, OrderStatus, OrderStatusHistory
from apps.orders.services.status_transitions import is_transition_allowed

if TYPE_CHECKING:
    from apps.users.models import User


_STATUS_TO_DATE_FIELD: dict[str, str] = {
    OrderStatus.PAID: "paid_at",
    OrderStatus.SHIPPED: "shipped_at",
    OrderStatus.DELIVERED: "delivered_at",
    OrderStatus.CANCELLED: "cancelled_at",
}


class OrderStatusService:
    """Сервис смены статусов заказа."""

    @staticmethod
    @transaction.atomic
    def change_status(
        order: Order,
        new_status: str,
        changed_by: "User | None" = None,
        comment: str = "",
    ) -> Order:
        """
        Сменить статус заказа с валидацией и побочными эффектами.

        Args:
            order: заказ для смены статуса
            new_status: целевой статус из OrderStatus
            changed_by: кто меняет (None для автоматических переходов)
            comment: комментарий к записи истории

        Returns:
            Обновлённый Order

        Raises:
            ValidationError("invalid_transition"): переход запрещён
                текущим графом состояний.
        """
        old_status = order.status
        product_type = order._get_product_type_for_transitions()

        if not is_transition_allowed(old_status, new_status, product_type):
            raise ValidationError(
                error_code="invalid_transition",
                message=f"Недопустимый переход статуса: {old_status} → {new_status}.",
            )

        order.status = new_status
        date_field = _STATUS_TO_DATE_FIELD.get(new_status)
        if date_field:
            setattr(order, date_field, timezone.now())

        order.save()

        if new_status == OrderStatus.CANCELLED:
            OrderStatusService._release_reserved_stock(order)

        OrderStatusHistory.objects.create(
            order=order,
            status_from=old_status,
            status_to=new_status,
            changed_by=changed_by,
            comment=comment,
            is_automatic=(changed_by is None),
        )

        return order

    @staticmethod
    def _release_reserved_stock(order: Order) -> None:
        """
        Уменьшить reserved_quantity для всех позиций отменённого заказа.

        F-expression гарантирует атомарность: reserved -= quantity
        выполняется в SQL без гонки.
        """
        for item in order.items.all():
            ProductStock.objects.filter(
                product=item.product,
                warehouse=order.warehouse,
            ).update(reserved_quantity=F("reserved_quantity") - item.quantity)
