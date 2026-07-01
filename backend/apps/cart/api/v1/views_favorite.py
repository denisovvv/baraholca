"""
Views API избранного.

FavoriteListView    — GET /api/v1/favorites/       — список избранного текущего пользователя
FavoriteCountView   — GET /api/v1/favorites/count/ — количество активных избранных
FavoriteDetailView  — PUT/DELETE /api/v1/favorites/{product_id}/ — добавить/убрать

Все endpoint-ы требуют аутентификации. Список и счётчик фильтруют
только активные и доступные к продаже товары (product.is_active=True,
product.is_available_for_sale=True), чтобы клиент не видел "спящие"
избранные, которые продавец временно снял с продажи.

PUT идемпотентен: повторный запрос по тому же product_id не даёт
ошибку — возвращает 200 если уже было, 201 если создали.

DELETE идемпотентен: удаление несуществующей записи возвращает 204,
не 404 — клиенту не нужно знать было ли что удалять, важно чтобы
после запроса записи не было.
"""

from typing import ClassVar, cast

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.api.v1.serializers import FavoriteReadSerializer
from apps.cart.models import Favorite
from apps.catalog.models import Product
from apps.common.exceptions import NotFoundError
from apps.users.models import User


class FavoriteListView(APIView):
    """
    GET /api/v1/favorites/ — список избранного текущего пользователя.

    Возвращает только записи, где товар активен и доступен к продаже.
    Записи с временно скрытыми товарами остаются в БД, но не показываются —
    когда продавец вернёт товар в активные, он снова появится в списке.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        favorites = Favorite.objects.filter(
            user=user,
            product__is_active=True,
            product__is_available_for_sale=True,
        ).select_related("product", "product__seller", "product__category")

        serializer = FavoriteReadSerializer(
            favorites,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class FavoriteCountView(APIView):
    """
    GET /api/v1/favorites/count/ — количество избранных товаров.

    Считает только те, которые пользователь увидит в списке
    (активные и доступные к продаже). Согласованность гарантирована:
    count и list всегда возвращают одну и ту же цифру.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        count = Favorite.objects.filter(
            user=user,
            product__is_active=True,
            product__is_available_for_sale=True,
        ).count()
        return Response({"count": count}, status=status.HTTP_200_OK)


class FavoriteDetailView(APIView):
    """
    PUT /api/v1/favorites/{product_id}/    — добавить товар в избранное.
    DELETE /api/v1/favorites/{product_id}/ — убрать товар из избранного.

    PUT идемпотентен:
    - если товара нет — создаём, возвращаем 201 + тело
    - если товар уже был — возвращаем 200 + тело (ничего не изменилось)
    - если товар не существует в БД — 404 product_not_found

    DELETE идемпотентен:
    - если запись есть — удаляем, возвращаем 204
    - если записи нет — возвращаем 204 (цель "убрать" достигнута)

    Мы НЕ фильтруем по is_active в PUT — товар может быть временно
    скрыт продавцом, но пользователь всё равно может отметить его
    как избранное на будущее. См. решение проекта.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def put(self, request: Request, product_id: int) -> Response:
        product = self._get_product_or_404(product_id)
        user = cast(User, request.user)

        favorite, created = Favorite.objects.get_or_create(
            user=user,
            product=product,
        )

        serializer = FavoriteReadSerializer(
            favorite,
            context={"request": request},
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=response_status)

    def delete(self, request: Request, product_id: int) -> Response:
        # Не проверяем существование Product — идемпотентно даже если
        # товара уже нет в БД (CASCADE удалил Favorite вместе с ним).
        user = cast(User, request.user)
        Favorite.objects.filter(
            user=user,
            product_id=product_id,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _get_product_or_404(product_id: int) -> Product:
        """
        Найти товар или бросить NotFoundError.

        Вынесено в staticmethod для явной документации, что
        мы возвращаем именно product_not_found (не generic 404).
        """
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise NotFoundError(
                "product_not_found",
                "Товар не найден.",
            ) from exc
