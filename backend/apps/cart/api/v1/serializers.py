"""
Сериализаторы API избранного и корзины.

FavoriteReadSerializer — представление записи избранного.

Cart:
- CartItemReadSerializer — одна позиция в корзине с полем is_available,
  чтобы клиент показывал недоступные товары помеченными.
- CartReadSerializer — корзина целиком: items, total_quantity, updated_at.
- CartItemWriteSerializer — приём quantity в PUT /cart/items/<product_id>/.
  quantity=0 семантически значит удалить позицию (валидируется как >= 0).
"""

from typing import ClassVar

from rest_framework import serializers

from apps.cart.models import Cart, CartItem, Favorite
from apps.catalog.api.v1.serializers import ProductListSerializer


class FavoriteReadSerializer(serializers.ModelSerializer):
    """
    Представление записи избранного для мобильного клиента.

    Разворачивает Product полностью — экрану "Моё избранное"
    достаточно одного запроса, чтобы показать список карточек.
    """

    product = ProductListSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields: ClassVar[list[str]] = [
            "added_at",
            "product",
        ]


class CartItemReadSerializer(serializers.ModelSerializer):
    """
    Позиция корзины для отображения клиенту.

    product разворачивается через ProductListSerializer.

    is_available — вычисляемое булево поле: клиент видит недоступные
    товары помеченными ("этот товар больше не продаётся, удалите").
    Товар недоступен если is_active=False или is_available_for_sale=False.
    """

    product = ProductListSerializer(read_only=True)
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields: ClassVar[list[str]] = [
            "product",
            "quantity",
            "added_at",
            "is_available",
        ]

    def get_is_available(self, obj: CartItem) -> bool:
        """
        True если товар доступен к покупке.
        Клиент использует этот флаг чтобы отобразить недоступные
        позиции визуально (например, серым цветом с подсказкой).
        """
        return obj.product.is_active and obj.product.is_available_for_sale


class CartReadSerializer(serializers.ModelSerializer):
    """
    Корзина целиком: позиции, общее количество товаров, дата обновления.

    total_quantity считается через сумму по всем позициям — используется
    в мобильном UI для бейджа корзины ("Корзина (7)"). items_count в теле
    не отдаётся здесь; он есть в отдельном endpoint GET /cart/count/.
    """

    items = CartItemReadSerializer(many=True, read_only=True)
    total_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields: ClassVar[list[str]] = [
            "items",
            "total_quantity",
            "updated_at",
        ]

    def get_total_quantity(self, obj: Cart) -> int:
        """
        Сумма quantity по всем позициям.
        Считаем в Python, а не отдельным SQL — все items уже загружены
        для сериализации, дополнительный запрос не нужен.
        """
        return sum(item.quantity for item in obj.items.all())


class CartItemWriteSerializer(serializers.Serializer):
    """
    Приём quantity в PUT /api/v1/cart/items/<product_id>/.

    quantity=0 валиден: семантически означает "удалить позицию",
    во view обрабатывается как DELETE. Отрицательные значения
    отклоняются на уровне сериализатора (min_value=0).
    """

    quantity = serializers.IntegerField(min_value=0)
