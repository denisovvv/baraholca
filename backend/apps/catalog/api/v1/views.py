"""
API views для каталога: категории, склады, товары.
"""

from rest_framework import filters, generics
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError

from django.db.models import Case, DecimalField, F, When
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from apps.catalog.api.v1.serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    WarehouseListSerializer,
    WarehouseNearbySerializer,
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
    
class WarehouseNearbyView(generics.ListAPIView):
    """
    Склады, отсортированные по расстоянию до точки покупателя.

    Параметры (обязательные):
        ?lat=<широта>   — например 51.66
        ?lon=<долгота>  — например 39.20

    Возвращает активные склады с полем distance_km,
    отсортированные от ближайшего к дальнему.

    GET /api/v1/catalog/warehouses/nearby/?lat=51.66&lon=39.20
    """

    serializer_class = WarehouseNearbySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        lat = self.request.query_params.get('lat')
        lon = self.request.query_params.get('lon')

        # Проверяем, что координаты переданы
        if lat is None or lon is None:
            raise ValidationError(
                'Укажите координаты: ?lat=<широта>&lon=<долгота>'
            )

        # Проверяем, что координаты — числа в допустимом диапазоне
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            raise ValidationError('Координаты должны быть числами')

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValidationError(
                'Координаты вне допустимого диапазона '
                '(широта -90..90, долгота -180..180)'
            )

        # Точка покупателя. ВАЖНО: Point(долгота, широта) — x, y
        user_location = Point(lon, lat, srid=4326)

        # Аннотируем расстояние и сортируем по нему
        return Warehouse.objects.filter(
            is_active=True,
        ).annotate(
            distance=Distance('location', user_location),
        ).select_related('seller').order_by('distance')