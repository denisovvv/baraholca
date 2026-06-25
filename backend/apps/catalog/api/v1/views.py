"""
API views для каталога: категории, склады, товары.
"""

from typing import ClassVar

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db.models import Case, DecimalField, F, When
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, BasePermission

from apps.catalog.api.v1.filters import ProductFilter
from apps.catalog.api.v1.serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    WarehouseListSerializer,
    WarehouseNearbySerializer,
)
from apps.catalog.models import Category, Product, Warehouse


class CategoryListView(generics.ListAPIView):
    """
    Список всех активных категорий каталога.
    """

    serializer_class = CategorySerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    pagination_class = None  # категорий немного, пагинация не нужна

    def get_queryset(self):
        return Category.objects.filter(
            is_active=True,
        ).order_by("order", "name")


class WarehouseListView(generics.ListAPIView):
    """
    Список всех активных складов.
    """

    serializer_class = WarehouseListSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    pagination_class = None  # складов немного

    def get_queryset(self):
        """Активные склады, отсортированные по имени."""
        return (
            Warehouse.objects.filter(
                is_active=True,
            )
            .select_related("seller")
            .order_by("name")
        )


class ProductDetailView(generics.RetrieveAPIView):
    """
    Карточка одного товара со всеми деталями.
    """

    serializer_class = ProductDetailSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    lookup_field = "id"

    def get_queryset(self):
        """
        Только товары, видимые в каталоге.
        """
        return (
            Product.objects.filter(
                is_active=True,
                is_available_for_sale=True,
            )
            .select_related(
                "seller",
                "category",
            )
            .prefetch_related(
                "images",
                "stocks__warehouse",
            )
        )


class ProductListView(generics.ListAPIView):
    """
    Список товаров с фильтрацией, поиском и пагинацией.
    """

    serializer_class = ProductListSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    filterset_class = ProductFilter
    search_fields: ClassVar[list[str]] = ["name_short", "name_full"]
    ordering_fields: ClassVar[list[str]] = ["effective_price_anno", "name_short"]
    ordering: ClassVar[list[str]] = ["name_short"]  # сортировка по умолчанию

    def get_queryset(self):
        """
        Товары, видимые в каталоге, с аннотацией эффективной цены.
        """
        return (
            Product.objects.filter(
                is_active=True,
                is_available_for_sale=True,
            )
            .select_related(
                "seller",
                "category",
            )
            .prefetch_related(
                "images",
            )
            .annotate(
                effective_price_anno=Case(
                    When(discount_price__isnull=False, then=F("discount_price")),
                    default=F("base_price"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )


class WarehouseNearbyView(generics.ListAPIView):
    """
    Склады, отсортированные по расстоянию до точки покупателя.
    """

    serializer_class = WarehouseNearbySerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        lat = self.request.query_params.get("lat")
        lon = self.request.query_params.get("lon")

        # Проверяем, что координаты переданы
        if lat is None or lon is None:
            raise ValidationError("Укажите координаты: ?lat=<широта>&lon=<долгота>")

        # Проверяем, что координаты — числа в допустимом диапазоне
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            raise ValidationError("Координаты должны быть числами")

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValidationError(
                "Координаты вне допустимого диапазона (широта -90..90, долгота -180..180)"
            )

        # Точка покупателя. ВАЖНО: Point(долгота, широта) — x, y
        user_location = Point(lon, lat, srid=4326)

        # Аннотируем расстояние и сортируем по нему
        return (
            Warehouse.objects.filter(
                is_active=True,
            )
            .annotate(
                distance=Distance("location", user_location),
            )
            .select_related("seller")
            .order_by("distance")
        )


class CategoryTreeView(generics.ListAPIView):
    """
    Дерево категорий каталога.
    """

    serializer_class = CategoryTreeSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(
            is_active=True,
            parent__isnull=True,
        ).order_by("order", "name")
