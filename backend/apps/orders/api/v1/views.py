"""
Views API заказов.

CheckoutView — POST /api/v1/orders/ для оформления заказа.
Валидация → CheckoutService → 201 со списком созданных Order.
"""

from typing import ClassVar, cast

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.api.v1.serializers import (
    CheckoutRequestSerializer,
    OrderReadSerializer,
)
from apps.orders.services.checkout import CheckoutService
from apps.users.models import User


class CheckoutView(APIView):
    """
    POST /api/v1/orders/ — оформление заказа.

    Тело валидируется через CheckoutRequestSerializer с условной
    проверкой полей по delivery_method. CheckoutService выполняет
    всю бизнес-логику в одной транзакции. Возвращаем 201 со списком
    созданных Order (может быть 1 или несколько).
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def post(self, request: Request) -> Response:
        request_serializer = CheckoutRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        orders = CheckoutService.perform_checkout(
            user=cast(User, request.user),
            payload=dict(request_serializer.validated_data),
        )

        response_serializer = OrderReadSerializer(orders, many=True, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
