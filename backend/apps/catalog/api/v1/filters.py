"""
Фильтры для API каталога.
"""

from typing import ClassVar

import django_filters  # type: ignore[import-untyped]

from apps.catalog.models import Product


class ProductFilter(django_filters.FilterSet):  # type: ignore[misc]
    """
    Фильтрация товаров: категория, продавец, диапазон цен, тип товара,
    минимальный рейтинг, наличие скидки.
    """

    price_min = django_filters.NumberFilter(
        field_name="effective_price_anno",
        lookup_expr="gte",
    )
    price_max = django_filters.NumberFilter(
        field_name="effective_price_anno",
        lookup_expr="lte",
    )
    # Минимальный рейтинг: rating_avg — аннотация из get_catalog_queryset.
    # Товары без отзывов (rating_avg=None) при фильтре по рейтингу
    # не попадают в выборку (None не проходит >=).
    rating_min = django_filters.NumberFilter(
        field_name="rating_avg",
        lookup_expr="gte",
    )
    # Только со скидкой: discount_price задан (не null).
    has_discount = django_filters.BooleanFilter(
        field_name="discount_price",
        lookup_expr="isnull",
        exclude=True,
    )

    class Meta:
        model = Product
        fields: ClassVar[list[str]] = ["category", "seller", "product_type"]
