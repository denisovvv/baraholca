"""
API views корзины пользователя.

CartView       — GET /api/v1/cart/           — получить свою корзину
                 DELETE /api/v1/cart/         — очистить корзину
CartCountView  — GET /api/v1/cart/count/     — счётчик (items_count, total_quantity)
CartItemView   — PUT /api/v1/cart/items/<product_id>/    — добавить/обновить позицию
                 DELETE /api/v1/cart/items/<product_id>/  — удалить позицию

Все endpoint-ы требуют аутентификации.

GET /cart/ работает даже если корзины ещё нет в БД: возвращаем
пустую структуру, не создавая запись. Cart создаётся лениво через
CartManager.get_or_create_for_user при первом PUT позиции.

PUT с quantity=0 семантически значит "удалить" — обрабатывается
как DELETE (по решению проекта Q2).

Неактивный товар (is_active=False или is_available_for_sale=False)
в PUT отклоняется с 422 product_unavailable — корзина = "хочу купить
сейчас", смысла в неактивных товарах нет. Уже добавленные позиции с
неактивными товарами остаются в корзине с флагом is_available=False.
"""

from typing import ClassVar, cast

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.api.v1.serializers import (
    CartItemWriteSerializer,
    CartReadSerializer,
)
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product
from apps.common.exceptions import NotFoundError, ValidationError
from apps.users.models import User


class CartView(APIView):
    """
    GET  /api/v1/cart/  — получить корзину пользователя.
    DELETE /api/v1/cart/ — очистить корзину (удалить все позиции).

    Если корзины в БД ещё нет, GET вернёт пустую структуру, а не 404.
    Пользователь всегда "имеет" корзину с точки зрения API —
    просто она может быть пустой.

    DELETE идемпотентен: если корзины или позиций нет — 204.
    Сама Cart-запись при очистке не удаляется, только позиции.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        cart = (
            Cart.objects.filter(user=user)
            .prefetch_related(
                "items__product",
                "items__product__seller",
                "items__product__category",
            )
            .first()
        )

        if cart is None:
            return Response(
                {"items": [], "total_quantity": 0, "updated_at": None},
                status=status.HTTP_200_OK,
            )

        serializer = CartReadSerializer(cart, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request: Request) -> Response:
        user = cast(User, request.user)
        cart = Cart.objects.filter(user=user).first()

        if cart is not None:
            cart.items.all().delete()
            cart.save(update_fields=["updated_at"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class CartCountView(APIView):
    """
    GET /api/v1/cart/count/ — счётчик корзины.

    Возвращает:
        items_count    — число уникальных товаров в корзине
                         (для карточек на экране корзины)
        total_quantity — сумма quantity по всем позициям
                         (для бейджа "Корзина (7)" в шапке)

    Считает через агрегацию в SQL — эффективно, не сериализуем items.
    Пустая корзина или отсутствие Cart возвращает нулевые значения.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        items_qs = CartItem.objects.filter(cart__user=user)
        items_count = items_qs.count()
        total_quantity = sum(item.quantity for item in items_qs)
        return Response(
            {"items_count": items_count, "total_quantity": total_quantity},
            status=status.HTTP_200_OK,
        )


class CartItemView(APIView):
    """
    PUT    /api/v1/cart/items/<product_id>/ — добавить или обновить позицию.
    DELETE /api/v1/cart/items/<product_id>/ — удалить позицию.

    PUT принимает тело {"quantity": N}:
      - Если Product не существует → 404 product_not_found
      - Если Product неактивен или не в продаже → 422 product_unavailable
      - Если quantity=0 → удаляется существующая позиция (идемпотентно)
      - Если quantity>0 → устанавливается новое значение
        (не увеличивается, а именно устанавливается — PUT-семантика)

    После любой модификации возвращается корзина целиком (CartReadSerializer),
    чтобы клиент получил актуальное состояние без дополнительного GET.

    DELETE идемпотентен: удаление несуществующей позиции возвращает 204.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def put(self, request: Request, product_id: int) -> Response:
        user = cast(User, request.user)
        product = self._get_product_or_404(product_id)
        self._reject_if_unavailable(product)

        write_serializer = CartItemWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        quantity = write_serializer.validated_data["quantity"]

        if quantity == 0:
            CartItem.objects.filter(cart__user=user, product=product).delete()
            return self._return_cart(user, request)

        cart = Cart.objects.get_or_create_for_user(user)
        CartItem.objects.update_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity},
        )
        cart.save(update_fields=["updated_at"])

        return self._return_cart(user, request)

    def delete(self, request: Request, product_id: int) -> Response:
        user = cast(User, request.user)
        CartItem.objects.filter(cart__user=user, product_id=product_id).delete()

        cart = Cart.objects.filter(user=user).first()
        if cart is not None:
            cart.save(update_fields=["updated_at"])

        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _get_product_or_404(product_id: int) -> Product:
        """
        Найти товар или бросить NotFoundError.
        """
        try:
            return Product.objects.get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise NotFoundError(
                "product_not_found",
                "Товар не найден.",
            ) from exc

    @staticmethod
    def _reject_if_unavailable(product: Product) -> None:
        """
        Отклонить операцию с неактивным товаром.
        """
        if not product.is_active or not product.is_available_for_sale:
            raise ValidationError(
                "product_unavailable",
                "Товар недоступен для покупки.",
            )

    @staticmethod
    def _return_cart(user: User, request: Request) -> Response:
        """
        Вернуть текущее состояние корзины пользователя.
        """
        cart = (
            Cart.objects.filter(user=user)
            .prefetch_related(
                "items__product",
                "items__product__seller",
                "items__product__category",
            )
            .first()
        )
        if cart is None:
            return Response(
                {"items": [], "total_quantity": 0, "updated_at": None},
                status=status.HTTP_200_OK,
            )
        serializer = CartReadSerializer(cart, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
