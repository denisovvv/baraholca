"""
Сериализаторы API избранного.

FavoriteReadSerializer используется в GET /api/v1/favorites/ —
возвращает список записей с развёрнутым Product внутри,
чтобы клиент мог отрисовать карточки товаров без
дополнительных запросов на каждый товар.
"""

from typing import ClassVar

from rest_framework import serializers

from apps.cart.models import Favorite
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
