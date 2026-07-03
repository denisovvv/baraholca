"""
Views API заказов.

OrdersView — коллекция:
  POST /api/v1/orders/ — оформление заказа (checkout)
  GET  /api/v1/orders/ — список моих заказов с фильтрами

OrderDetailView — конкретный ресурс:
  GET  /api/v1/orders/{uuid}/ — детали одного заказа

Все endpoint-ы требуют аутентификации. Изоляция: пользователь видит
и оформляет только свои заказы.
"""

from typing import ClassVar, cast

from django.db.models import Count, QuerySet
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.api.v1.serializers import (
    CheckoutRequestSerializer,
    OrderListSerializer,
    OrderReadSerializer,
)
from apps.orders.models import Order
from apps.orders.services.checkout import CheckoutService
from apps.users.models import User


class OrdersView(APIView):
    """
    Коллекция заказов пользователя.

    POST — оформить заказ через CheckoutService.
    GET — получить список своих заказов с опциональными фильтрами:
        ?status=paid
        ?created_after=2026-01-01
        ?created_before=2026-12-31

    select_related на seller/warehouse и annotate items_count
    оптимизируют список от N+1 при рендере страницы.
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
        """
        Базовый queryset пользователя с фильтрами.
        Оптимизации: select_related на связанные объекты,
        annotate для подсчёта позиций в одном SQL.
        """
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

    Lookup по uuid (публичный ID, безопаснее чем внутренний id).
    Возвращаем полный OrderReadSerializer с nested items и warehouse.
    Изоляция: filter(user=...) не даст доступа к чужим заказам,
    404 вместо 403 не раскрывает существование чужого заказа.
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
