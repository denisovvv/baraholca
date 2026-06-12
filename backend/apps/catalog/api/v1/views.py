"""
API views для каталога: категории, склады, товары.
"""

from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.catalog.api.v1.serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    WarehouseListSerializer,
)
from apps.catalog.models import Category, Product, Warehouse

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