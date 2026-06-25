"""
Фильтры для API каталога.
"""

from typing import ClassVar

import django_filters

from apps.catalog.models import Product


class ProductFilter(django_filters.FilterSet):
    """
    Фильтрация товаров по категории, продавцу и диапазону цен.
    """

    price_min = django_filters.NumberFilter(
        field_name="effective_price_anno",
        lookup_expr="gte",
    )
    price_max = django_filters.NumberFilter(
        field_name="effective_price_anno",
        lookup_expr="lte",
    )

    class Meta:
        model = Product
        fields: ClassVar[list[str]] = ["category", "seller"]
