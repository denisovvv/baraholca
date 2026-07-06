"""
Views API отзывов.

ReviewsView — коллекция:
  GET  /api/v1/reviews/?product={id} — список отзывов товара (публично)
  POST /api/v1/reviews/              — создать отзыв (авторизованный)

ReviewDetailView — конкретный отзыв:
  PATCH  /api/v1/reviews/{id}/ — редактировать свой
  DELETE /api/v1/reviews/{id}/ — удалить свой

Список публичен (отзывы видят все). Создание/изменение/удаление —
только авторизованный автор своих отзывов.
"""

from typing import ClassVar, cast

from django.db.models import QuerySet
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews.api.v1.serializers import (
    ReviewCreateSerializer,
    ReviewReadSerializer,
    ReviewUpdateSerializer,
)
from apps.reviews.models import Review
from apps.users.models import User


class ReviewsView(APIView):
    """
    Коллекция отзывов.

    GET — список отзывов товара по ?product={id}, публично.
    POST — создать отзыв, только авторизованный (проверка покупки
    в сериализаторе).
    """

    def get_permissions(self) -> list[BasePermission]:
        """GET публичен, POST требует авторизации."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request: Request) -> Response:
        """Список отзывов товара по ?product={id}."""
        product_id = request.query_params.get("product")
        # Публичный список — только опубликованные отзывы (модерация
        # скрывает неуместные через is_published=False).
        qs = Review.objects.select_related("user").filter(is_published=True)
        if product_id:
            qs = qs.filter(product_id=product_id)

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = ReviewReadSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        """Создать отзыв от текущего пользователя."""
        serializer = ReviewCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        review = serializer.save(user=cast(User, request.user))

        read_serializer = ReviewReadSerializer(review, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Конкретный отзыв: редактирование и удаление своего.

    PATCH/PUT — обновить (ReviewUpdateSerializer, только rating/text).
    DELETE — удалить.
    Изоляция: filter(user=...) → 404 для чужого отзыва.
    GET одного отзыва тоже доступен (RetrieveUpdateDestroy включает).
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def get_queryset(self) -> QuerySet[Review]:
        user = cast(User, self.request.user)
        return Review.objects.filter(user=user).select_related("user")

    def get_serializer_class(self) -> type:
        """Чтение — Read, изменение — Update."""
        if self.request.method in ("PATCH", "PUT"):
            return ReviewUpdateSerializer
        return ReviewReadSerializer
