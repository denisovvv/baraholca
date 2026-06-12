"""
Фильтры для API каталога.

Используется django-filter для декларативного описания фильтрации.
"""

import django_filters

from apps.catalog.models import Product


class ProductFilter(django_filters.FilterSet):
    """
    Фильтрация товаров по категории, продавцу и диапазону цен.

    Цена фильтруется по эффективной цене (со скидкой), а не базовой,
    потому что покупатель ищет по той цене, которую реально заплатит.
    Для этого используется аннотированное поле effective_price из queryset.
    """

    price_min = django_filters.NumberFilter(
        field_name='effective_price_anno',
        lookup_expr='gte',
    )
    price_max = django_filters.NumberFilter(
        field_name='effective_price_anno',
        lookup_expr='lte',
    )

    class Meta:
        model = Product
        fields = ['category', 'seller']