"""
API views для каталога: категории, склады, товары.
"""

from typing import ClassVar

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db.models import Avg, Case, Count, DecimalField, F, Q, QuerySet, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny, BasePermission

from apps.catalog.api.v1.filters import ProductFilter
from apps.catalog.api.v1.serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductSuggestSerializer,
    WarehouseListSerializer,
    WarehouseNearbySerializer,
)
from apps.catalog.models import Category, Product, Warehouse
from apps.common.exceptions import ValidationError
from apps.orders.models import OrderItem, OrderStatus

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


def get_catalog_queryset() -> QuerySet[Product]:
    """
    Базовый queryset товаров каталога с аннотациями.

    Одна точка правды для всех вьюх каталога (список, рекомендации):
    фильтр видимости (активные + доступные), эффективная цена
    (скидочная или базовая), агрегированный рейтинг и число
    опубликованных отзывов.
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
            rating_sort=Coalesce(
                Avg(
                    "reviews__rating",
                    filter=Q(reviews__is_published=True),
                ),
                0.0,
            ),
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
    ordering_fields: ClassVar[list[str]] = [
        "effective_price_anno",
        "name_short",
        "rating_sort",
        "created_at",
    ]
    ordering: ClassVar[list[str]] = ["name_short"]  # сортировка по умолчанию

    def get_queryset(self) -> QuerySet[Product]:
        """Товары, видимые в каталоге, с аннотациями цены и рейтинга."""
        return get_catalog_queryset()


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


class SellerProductsView(generics.ListAPIView):
    """
    Другие товары того же продавца — блок "Ещё у этого продавца"
    на карточке товара.

    Берёт продавца у товара из URL и отдаёт другие его активные
    товары, исключая текущий. Лимит задаётся пагинацией/срезом —
    это рекомендательный блок, не полный каталог продавца.
    """

    serializer_class = ProductListSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None

    # Сколько товаров показывать в блоке рекомендаций.
    RECOMMENDATIONS_LIMIT = 10

    def get_queryset(self) -> QuerySet[Product]:
        """
        Товары того же продавца, что и товар из URL, кроме него самого.

        Если товар не найден — 404 (через get_object_or_404).
        Переиспользуем общий queryset каталога, чтобы карточки
        рекомендаций имели те же данные (цена, рейтинг), что и в списке.
        """
        product = get_object_or_404(Product, pk=self.kwargs["product_id"])
        return (
            get_catalog_queryset()
            .filter(
                seller_id=product.seller_id,
            )
            .exclude(
                pk=product.pk,
            )[: self.RECOMMENDATIONS_LIMIT]
        )


class SimilarProductsView(generics.ListAPIView):
    """
    Похожие товары — блок "Похожие товары" на карточке товара.

    Берёт категорию у товара из URL и отдаёт другие товары той же
    категории, исключая текущий. Если у товара нет категории —
    пустой список (похожих по категории нет).
    """

    serializer_class = ProductListSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None

    # Сколько товаров показывать в блоке рекомендаций.
    RECOMMENDATIONS_LIMIT = 10

    def get_queryset(self) -> QuerySet[Product]:
        """
        Товары той же категории, что и товар из URL, кроме него самого.

        Если товар не найден — 404. Если у товара нет категории —
        пустой queryset. Переиспользуем общий queryset каталога.
        """
        product = get_object_or_404(Product, pk=self.kwargs["product_id"])
        if product.category_id is None:
            return get_catalog_queryset().none()
        return (
            get_catalog_queryset()
            .filter(
                category_id=product.category_id,
            )
            .exclude(
                pk=product.pk,
            )[: self.RECOMMENDATIONS_LIMIT]
        )


class ProductSuggestView(generics.ListAPIView):
    """
    Автодополнение поиска — подсказки по вводу.

    GET /api/v1/catalog/products/suggest/?q=чех
    Возвращает до 8 активных товаров, в названии которых (кратком или
    полном) встречается запрос. Пустой или короткий запрос — пустой
    список. Ответ компактный (id + name_short).
    """

    serializer_class = ProductSuggestSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None

    # Максимум подсказок в выдаче.
    SUGGEST_LIMIT = 8
    # Минимальная длина запроса, чтобы искать (1 символ — уже ищем).
    MIN_QUERY_LENGTH = 1

    def get_queryset(self) -> QuerySet[Product]:
        """
        Активные товары, чьё название содержит запрос (icontains).

        Поиск по name_short и name_full (как основной search).
        Пустой/слишком короткий запрос — пустой queryset.
        """
        query = self.request.query_params.get("q", "").strip()
        if len(query) < self.MIN_QUERY_LENGTH:
            return Product.objects.none()
        return (
            Product.objects.filter(
                is_active=True,
                is_available_for_sale=True,
            )
            .filter(
                Q(name_short__icontains=query) | Q(name_full__icontains=query),
            )
            .order_by("name_short")[: self.SUGGEST_LIMIT]
        )


class BoughtTogetherView(generics.ListAPIView):
    """
    Товары, которые покупают вместе с текущим — блок "Покупают вместе".

    Аналитика по доставленным заказам: находим заказы (status=delivered),
    где есть текущий товар, берём другие товары из этих заказов и
    сортируем по частоте совместных покупок. Топ-20.

    Если совместных покупок нет (мало заказов) — пустой список.
    """

    serializer_class = ProductListSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]
    pagination_class = None

    BOUGHT_TOGETHER_LIMIT = 20

    def get_queryset(self) -> QuerySet[Product]:
        """
        Товары из доставленных заказов, содержащих текущий товар,
        кроме него самого, отсортированные по частоте совместных покупок.
        """
        product = get_object_or_404(Product, pk=self.kwargs["product_id"])
        # id доставленных заказов, где есть текущий товар.
        order_ids = (
            OrderItem.objects.filter(
                product_id=product.pk,
                order__status=OrderStatus.DELIVERED,
            )
            .values_list("order_id", flat=True)
            .distinct()
        )
        # Другие товары из этих заказов, по частоте (сколько заказов).
        return (
            get_catalog_queryset()
            .filter(order_items__order_id__in=order_ids)
            .exclude(pk=product.pk)
            .annotate(
                bought_freq=Count(
                    "order_items__order_id",
                    filter=Q(order_items__order_id__in=order_ids),
                    distinct=True,
                ),
            )
            .order_by("-bought_freq", "name_short")[: self.BOUGHT_TOGETHER_LIMIT]
        )
