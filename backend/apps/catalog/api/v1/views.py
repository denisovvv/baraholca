"""
API views для каталога: категории, склады, товары.
"""

from typing import ClassVar

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db.models import Avg, Case, Count, DecimalField, F, Q, QuerySet, When
from rest_framework import generics
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
from apps.common.exceptions import ValidationError

# Допустимые диапазоны географических координат (WGS84, SRID 4326).
LATITUDE_MIN = -90.0
LATITUDE_MAX = 90.0
LONGITUDE_MIN = -180.0
LONGITUDE_MAX = 180.0


class CategoryListView(generics.ListAPIView):
    """
    Список всех активных категорий каталога.
    """

    serializer_class = CategorySerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None  # категорий немного, пагинация не нужна

    def get_queryset(self) -> QuerySet[Category]:
        return Category.objects.filter(
            is_active=True,
        ).order_by("order", "name")


class WarehouseListView(generics.ListAPIView):
    """
    Список всех активных складов.
    """

    serializer_class = WarehouseListSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None  # складов немного

    def get_queryset(self) -> QuerySet[Warehouse]:
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
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[Product]:
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
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    filterset_class = ProductFilter
    search_fields: ClassVar[list[str]] = ["name_short", "name_full"]
    ordering_fields: ClassVar[list[str]] = ["effective_price_anno", "name_short"]
    ordering: ClassVar[list[str]] = ["name_short"]  # сортировка по умолчанию

    def get_queryset(self) -> QuerySet[Product]:
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
                ),
                rating_avg=Avg(
                    "reviews__rating",
                    filter=Q(reviews__is_published=True),
                ),
                reviews_count=Count(
                    "reviews",
                    filter=Q(reviews__is_published=True),
                ),
            )
        )


class WarehouseNearbyView(generics.ListAPIView):
    """
    Склады, отсортированные по расстоянию до точки покупателя.
    """

    serializer_class = WarehouseNearbySerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None

    def get_queryset(self) -> QuerySet[Warehouse]:
        lat_str = self.request.query_params.get("lat")
        lon_str = self.request.query_params.get("lon")

        if lat_str is None or lon_str is None:
            raise ValidationError(
                "coordinates_missing",
                "Укажите координаты: ?lat=<широта>&lon=<долгота>",
            )

        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError as exc:
            raise ValidationError(
                "coordinates_not_numeric",
                "Координаты должны быть числами",
            ) from exc

        if not (LATITUDE_MIN <= lat <= LATITUDE_MAX) or not (LONGITUDE_MIN <= lon <= LONGITUDE_MAX):
            raise ValidationError(
                "coordinates_out_of_range",
                "Координаты вне допустимого диапазона (широта -90..90, долгота -180..180)",
            )

        # Точка покупателя. ВАЖНО: Point(долгота, широта) — x, y
        user_location = Point(lon, lat, srid=4326)

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
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None

    def get_queryset(self) -> QuerySet[Category]:
        return Category.objects.filter(
            is_active=True,
            parent__isnull=True,
        ).order_by("order", "name")
