"""
Сериализаторы API заказов.

CheckoutRequestSerializer — приём тела POST /api/v1/orders/,
условная валидация по delivery_method (courier vs pickup).

CancelOrderSerializer — приём тела POST /api/v1/orders/{uuid}/cancel/,
опциональный comment для истории статусов.

OrderReadSerializer, OrderItemReadSerializer, OrderListSerializer —
отдача заказа клиенту в разных форматах.
"""

from typing import Any, ClassVar

from rest_framework import serializers

from apps.catalog.api.v1.serializers import (
    ProductListSerializer,
    WarehouseDetailSerializer,
)
from apps.orders.models import (
    DeliveryMethod,
    Order,
    OrderItem,
    PaymentMethod,
)


class CheckoutRequestSerializer(serializers.Serializer):
    """
    Приём тела POST /api/v1/orders/.

    Условная валидация по delivery_method: для courier обязательны
    адрес и координаты, для pickup — warehouse_uuid. Лишние поля
    не отклоняются — сервер использует только нужные.
    """

    delivery_method = serializers.ChoiceField(choices=DeliveryMethod.choices)
    delivery_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    delivery_latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    delivery_longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    delivery_comment = serializers.CharField(required=False, allow_blank=True)
    warehouse_uuid = serializers.UUIDField(required=False)
    recipient_name = serializers.CharField(max_length=150)
    recipient_phone = serializers.CharField(max_length=20)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        method = data.get("delivery_method")
        errors: dict[str, str] = {}
        if method == DeliveryMethod.COURIER:
            if not data.get("delivery_address"):
                errors["delivery_address"] = "Обязательно для доставки курьером."
            if data.get("delivery_latitude") is None:
                errors["delivery_latitude"] = "Обязательно для доставки курьером."
            if data.get("delivery_longitude") is None:
                errors["delivery_longitude"] = "Обязательно для доставки курьером."
        elif method == DeliveryMethod.PICKUP:
            if not data.get("warehouse_uuid"):
                errors["warehouse_uuid"] = "Обязательно для самовывоза."
        if errors:
            raise serializers.ValidationError(errors)
        return data


class CancelOrderSerializer(serializers.Serializer):
    """
    Приём тела POST /api/v1/orders/{uuid}/cancel/.

    Комментарий опциональный — попадёт в OrderStatusHistory.comment
    для аудита причин отмены.
    """

    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class OrderItemReadSerializer(serializers.ModelSerializer):
    """
    Позиция заказа с nested product.

    Snapshot-поля (name, price, sum) отдаются как хранятся — они
    не меняются после создания заказа даже если Product поменяется.
    """

    product = ProductListSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields: ClassVar[list[str]] = [
            "product",
            "product_name_snapshot",
            "product_uuid_1c",
            "quantity",
            "price",
            "sum",
        ]


class OrderReadSerializer(serializers.ModelSerializer):
    """Полное представление заказа для клиента."""

    items = OrderItemReadSerializer(many=True, read_only=True)
    warehouse = WarehouseDetailSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    delivery_method_display = serializers.CharField(
        source="get_delivery_method_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = Order
        fields: ClassVar[list[str]] = [
            "uuid",
            "number",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "delivery_method",
            "delivery_method_display",
            "delivery_address",
            "delivery_latitude",
            "delivery_longitude",
            "delivery_comment",
            "recipient_name",
            "recipient_phone",
            "payment_method",
            "payment_method_display",
            "subtotal",
            "delivery_cost",
            "total",
            "comment",
            "warehouse",
            "items",
            "created_at",
            "updated_at",
            "paid_at",
            "shipped_at",
            "delivered_at",
            "cancelled_at",
        ]


class OrderListSerializer(serializers.ModelSerializer):
    """
    Короткий формат для списка заказов.

    Без items и полного warehouse — только сводка. Клиент по клику
    открывает detail. items_count берётся из annotate в queryset.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    seller_name = serializers.CharField(source="seller.short_name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields: ClassVar[list[str]] = [
            "uuid",
            "number",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "seller_name",
            "warehouse_name",
            "total",
            "items_count",
            "created_at",
        ]
