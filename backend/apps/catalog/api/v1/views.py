"""
API views для каталога: категории, склады, товары.
"""

from rest_framework import filters, generics
from rest_framework.permissions import AllowAny

from django.db.models import Case, DecimalField, F, When

from apps.catalog.api.v1.serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    WarehouseListSerializer,
)
from apps.catalog.models import Category, Product, Warehouse
from apps.catalog.api.v1.filters import ProductFilter

class CategoryListView(generics.ListAPIView):
    """
    Список всех активных категорий каталога.

    Публичный endpoint — доступен без авторизации.
    Категории сортируются по полю order (вручную выставляется в админке),
    затем по имени.

    GET /api/v1/catalog/categories/
    """

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None  # категорий немного, пагинация не нужна

    def get_queryset(self):
        """
        Возвращает только активные категории.
        Сортировка: сначала по полю order, потом по имени.
        """
        return Category.objects.filter(
            is_active=True,
        ).order_by('order', 'name')
    
class WarehouseListView(generics.ListAPIView):
    """
    Список всех активных складов.

    Публичный endpoint. Возвращает склады с координатами и адресами.
    Используется для отображения точек на карте и выбора самовывоза.

    GET /api/v1/catalog/warehouses/
    """

    serializer_class = WarehouseListSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # складов немного

    def get_queryset(self):
        """Активные склады, отсортированные по имени."""
        return Warehouse.objects.filter(
            is_active=True,
        ).select_related('seller').order_by('name')
    
class ProductDetailView(generics.RetrieveAPIView):
    """
    Карточка одного товара со всеми деталями.

    Возвращает товар с фотографиями, остатками по складам,
    полным описанием и временем изготовления (для товаров под заказ).

    Показываются только товары, видимые в каталоге
    (активные и доступные к продаже).

    GET /api/v1/catalog/products/{id}/
    """

    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'

    def get_queryset(self):
        """
        Только товары, видимые в каталоге.

        select_related — подтягиваем продавца и категорию одним запросом.
        prefetch_related — фото и остатки (это связи "один ко многим",
        для них нужен prefetch, а не select_related).
        """
        return Product.objects.filter(
            is_active=True,
            is_available_for_sale=True,
        ).select_related(
            'seller',
            'category',
        ).prefetch_related(
            'images',
            'stocks__warehouse',
        )
    
class ProductListView(generics.ListAPIView):
    """
    Список товаров с фильтрацией, поиском и пагинацией.

    Параметры:
        ?category=<id>        — фильтр по категории
        ?seller=<id>          — фильтр по продавцу
        ?price_min=<число>    — минимальная эффективная цена
        ?price_max=<число>    — максимальная эффективная цена
        ?search=<текст>       — поиск по короткому и полному названию
        ?ordering=<поле>      — сортировка (effective_price_anno, name_short)
        ?page=<n>             — страница (по 20 товаров)

    Показываются только товары, видимые в каталоге.

    GET /api/v1/catalog/products/
    """

    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    filterset_class = ProductFilter
    search_fields = ['name_short', 'name_full']
    ordering_fields = ['effective_price_anno', 'name_short']
    ordering = ['name_short']  # сортировка по умолчанию

    def get_queryset(self):
        """
        Товары, видимые в каталоге, с аннотацией эффективной цены.

        effective_price_anno — вычисляемое в базе поле:
        discount_price если она задана, иначе base_price.
        Нужно, чтобы фильтровать и сортировать по реальной цене продажи.
        """
        return Product.objects.filter(
            is_active=True,
            is_available_for_sale=True,
        ).select_related(
            'seller',
            'category',
        ).prefetch_related(
            'images',
        ).annotate(
            effective_price_anno=Case(
                When(discount_price__isnull=False, then=F('discount_price')),
                default=F('base_price'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )