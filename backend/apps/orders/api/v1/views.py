"""
Views API заказов.

OrdersView — коллекция:
  POST /api/v1/orders/ — оформление заказа (checkout)
  GET  /api/v1/orders/ — список моих заказов с фильтрами

OrderDetailView — конкретный ресурс:
  GET  /api/v1/orders/{uuid}/ — детали одного заказа

OrderCancelView — команда отмены:
  POST /api/v1/orders/{uuid}/cancel/ — отменить свой заказ

Все endpoint-ы требуют аутентификации. Изоляция: пользователь
видит и меняет только свои заказы.
"""

from typing import ClassVar, cast

from django.db.models import Count, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ValidationError
from apps.orders.api.v1.serializers import (
    CancelOrderSerializer,
    CheckoutRequestSerializer,
    OrderListSerializer,
    OrderReadSerializer,
)
from apps.orders.models import Order, OrderStatus, PaymentStatus
from apps.orders.services.checkout import CheckoutService
from apps.orders.services.order_status import OrderStatusService
from apps.orders.services.payment_status import PaymentStatusService
from apps.users.models import User

# Статусы после которых покупатель не может отменить заказ:
# товар уже в пути или доставлен, отмена невозможна.
_STATUSES_FORBIDDEN_FOR_BUYER_CANCEL: frozenset[str] = frozenset(
    {
        OrderStatus.SHIPPED,
        OrderStatus.IN_DELIVERY,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
    }
)


class OrdersView(APIView):
    """
    Коллекция заказов пользователя.

    POST — оформить заказ через CheckoutService.
    GET — получить список своих заказов с опциональными фильтрами.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def post(self, request: Request) -> Response:
        """Оформление заказа (checkout)."""
        request_serializer = CheckoutRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        orders = CheckoutService.perform_checkout(
            user=cast(User, request.user),
            payload=dict(request_serializer.validated_data),
        )

        response_serializer = OrderReadSerializer(orders, many=True, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request: Request) -> Response:
        """Список заказов текущего пользователя с пагинацией и фильтрами."""
        qs = self._filtered_queryset(request)

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = OrderListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def _filtered_queryset(self, request: Request) -> QuerySet[Order]:
        user = cast(User, request.user)
        qs = (
            Order.objects.filter(user=user)
            .select_related("seller", "warehouse")
            .annotate(items_count=Count("items"))
            .order_by("-created_at")
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        created_after = request.query_params.get("created_after")
        if created_after:
            qs = qs.filter(created_at__gte=created_after)

        created_before = request.query_params.get("created_before")
        if created_before:
            qs = qs.filter(created_at__lte=created_before)

        return qs


class OrderDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/orders/{uuid}/ — детали одного заказа.

    Lookup по uuid. Изоляция: filter(user=...) не даст доступа
    к чужим заказам, 404 не раскрывает существование чужого заказа.
    """

    serializer_class = OrderReadSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]
    lookup_field = "uuid"

    def get_queryset(self) -> QuerySet[Order]:
        user = cast(User, self.request.user)
        return (
            Order.objects.filter(user=user)
            .select_related("seller", "warehouse")
            .prefetch_related(
                "items__product",
                "items__product__seller",
                "items__product__category",
            )
        )


class OrderCancelView(APIView):
    """
    POST /api/v1/orders/{uuid}/cancel/ — отменить свой заказ.

    Проверки:
    1. Заказ принадлежит текущему пользователю (иначе 404)
    2. Статус позволяет отмену покупателем (не после отгрузки)

    OrderStatusService сам:
    - валидирует переход через граф состояний
    - обновляет cancelled_at
    - освобождает reserved_quantity в ProductStock
    - создаёт запись OrderStatusHistory
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def post(self, request: Request, uuid: str) -> Response:
        user = cast(User, request.user)
        order = get_object_or_404(Order, uuid=uuid, user=user)

        if order.status in _STATUSES_FORBIDDEN_FOR_BUYER_CANCEL:
            raise ValidationError(
                error_code="cannot_cancel",
                message="Заказ нельзя отменить на текущем этапе.",
                details={"current_status": order.status},
            )

        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.validated_data.get("comment", "")

        OrderStatusService.change_status(
            order=order,
            new_status=OrderStatus.CANCELLED,
            changed_by=user,
            comment=comment,
        )

        order.refresh_from_db()
        response_serializer = OrderReadSerializer(order, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class OrderMarkPaidView(APIView):
    """
    POST /api/v1/orders/{uuid}/mark-paid/ — отметить заказ оплаченным.

    Заглушка вместо webhook эквайринга (пока его нет). Доступ только
    для is_staff (продавец/админ отмечает оплату вручную). В будущем
    заменится на автоматический webhook банка.

    PaymentStatusService валидирует переход, ставит paid_at,
    пишет PaymentStatusHistory. Изоляции по user нет — staff
    работает с любым заказом.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAdminUser]  # type: ignore[misc]

    def post(self, request: Request, uuid: str) -> Response:
        order = get_object_or_404(Order, uuid=uuid)

        PaymentStatusService.change_payment_status(
            order=order,
            new_status=PaymentStatus.PAID,
            changed_by=cast(User, request.user),
            comment="Отмечено вручную (mark-paid)",
        )

        order.refresh_from_db()
        serializer = OrderReadSerializer(order, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
