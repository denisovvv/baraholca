"""
Сериализаторы для API каталога: категории, склады, товары.
"""

from typing import Any, ClassVar, cast

from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Product,
    ProductCharacteristic,
    ProductImage,
    ProductStock,
    Warehouse,
)

# ============================================================================
# Category
# ============================================================================


class CategorySerializer(serializers.ModelSerializer):
    """
    Базовое представление категории.
    """

    parent_name = serializers.CharField(
        source="parent.name",
        read_only=True,
        allow_null=True,
    )
    full_path = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "slug",
            "parent",
            "parent_name",
            "full_path",
            "order",
        ]

    def get_full_path(self, obj: Category) -> str:
        return obj.get_full_path()


class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Категория с вложенными дочерними категориями (дерево).
    """

    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "slug",
            "order",
            "children",
        ]

    def get_children(self, obj: Category) -> list[dict[str, Any]]:
        """
        Рекурсивно сериализует активные дочерние категории.
        """
        children = obj.children.filter(is_active=True).order_by("order", "name")
        return cast(
            "list[dict[str, Any]]",
            CategoryTreeSerializer(children, many=True).data,
        )


# ============================================================================
# Warehouse
# ============================================================================


class WarehouseListSerializer(serializers.ModelSerializer):
    """
    Короткое представление склада для списков.
    """

    seller_name = serializers.CharField(
        source="seller.short_name",
        read_only=True,
    )
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "seller_name",
            "address",
            "latitude",
            "longitude",
            "pickup_available",
        ]

    def get_latitude(self, obj: Warehouse) -> float | None:
        """Широта."""
        return obj.location.y if obj.location else None

    def get_longitude(self, obj: Warehouse) -> float | None:
        """Долгота."""
        return obj.location.x if obj.location else None


class WarehouseDetailSerializer(WarehouseListSerializer):
    """
    Полное представление склада для карточки одного объекта.
    """

    class Meta(WarehouseListSerializer.Meta):
        fields: ClassVar[list[str]] = [
            *WarehouseListSerializer.Meta.fields,
            "contact_phone",
            "working_hours",
        ]


class WarehouseNearbySerializer(WarehouseListSerializer):
    """
    Склад с расстоянием до точки покупателя.
    """

    distance_km = serializers.SerializerMethodField()

    class Meta(WarehouseListSerializer.Meta):
        fields: ClassVar[list[str]] = [
            *WarehouseListSerializer.Meta.fields,
            "distance_km",
        ]

    def get_distance_km(self, obj: Warehouse) -> float | None:
        """
        Расстояние до склада в километрах, округлённое до 1 знака.
        """
        if hasattr(obj, "distance") and obj.distance is not None:
            return cast(float, round(obj.distance.km, 1))
        return None


# ============================================================================
# ProductImage
# ============================================================================


class ProductImageSerializer(serializers.ModelSerializer):
    """
    Фотография товара.
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields: ClassVar[list[str]] = [
            "id",
            "image_url",
            "order",
            "is_main",
        ]

    def get_image_url(self, obj: ProductImage) -> str | None:
        """Полный URL изображения с учётом домена."""
        request = self.context.get("request")
        if not obj.image:
            return None
        if request:
            return cast(str, request.build_absolute_uri(obj.image.url))
        return obj.image.url


# ============================================================================
# ProductStock
# ============================================================================


class ProductStockSerializer(serializers.ModelSerializer):
    """
    Остатки товара по складам.
    """

    warehouse_name = serializers.CharField(
        source="warehouse.name",
        read_only=True,
    )
    warehouse_address = serializers.CharField(
        source="warehouse.address",
        read_only=True,
    )
    available = serializers.SerializerMethodField()

    class Meta:
        model = ProductStock
        fields: ClassVar[list[str]] = [
            "warehouse_name",
            "warehouse_address",
            "available",
        ]

    def get_available(self, obj: ProductStock) -> bool:
        return obj.available_quantity > 0


# ============================================================================
# Product
# ============================================================================


class ProductSuggestSerializer(serializers.ModelSerializer):
    """
    Компактная подсказка автодополнения поиска: id + краткое название.
    Отдаётся списком при вводе запроса в поиск.
    """

    class Meta:
        model = Product
        fields: ClassVar[list[str]] = [
            "id",
            "name_short",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    """
    Короткое представление товара для списков и каталога.
    """

    seller_name = serializers.CharField(
        source="seller.short_name",
        read_only=True,
    )
    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
        allow_null=True,
    )
    main_image_url = serializers.SerializerMethodField()
    effective_price = serializers.DecimalField(
        source="get_effective_price",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    rating_avg = serializers.SerializerMethodField()
    reviews_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields: ClassVar[list[str]] = [
            "id",
            "name_short",
            "seller_name",
            "category_name",
            "main_image_url",
            "base_price",
            "discount_price",
            "effective_price",
            "product_type",
            "rating_avg",
            "reviews_count",
        ]

    def get_main_image_url(self, obj: Product) -> str | None:
        """
        URL главного фото товара.
        """
        main = obj.images.filter(is_main=True).first()
        if not main:
            main = obj.images.first()
        if not main:
            return None

        request = self.context.get("request")
        if request:
            return cast(str, request.build_absolute_uri(main.image.url))
        return main.image.url

    def get_rating_avg(self, obj: Product) -> float | None:
        """
        Средний балл товара из опубликованных отзывов, округлённый
        до 1 знака. None, если отзывов нет — фронт покажет "нет отзывов",
        а не "0.0".

        Значение приходит из аннотации rating_avg в queryset каталога.
        """
        value = getattr(obj, "rating_avg", None)
        if value is None:
            return None
        return round(float(value), 1)


class ProductCharacteristicSerializer(serializers.ModelSerializer):
    """Характеристика товара (название: значение) для карточки."""

    class Meta:
        model = ProductCharacteristic
        fields: ClassVar[list[str]] = [
            "name",
            "value",
        ]


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Компактное представление варианта товара для переключателя на
    карточке. Каждый вариант — отдельный товар (Product) со своей
    ценой, доступностью и атрибутами (цвет/размер).
    """

    effective_price = serializers.DecimalField(
        source="get_effective_price",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    main_image_url = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields: ClassVar[list[str]] = [
            "id",
            "name_short",
            "variant_color",
            "variant_size",
            "effective_price",
            "main_image_url",
            "is_available",
        ]

    def get_main_image_url(self, obj: Product) -> str | None:
        """URL главного фото варианта."""
        main = obj.images.filter(is_main=True).first()
        if not main:
            main = obj.images.first()
        if not main:
            return None
        request = self.context.get("request")
        if request:
            return cast(str, request.build_absolute_uri(main.image.url))
        return main.image.url

    def get_is_available(self, obj: Product) -> bool:
        """Доступен ли вариант к покупке."""
        return obj.is_active and obj.is_available_for_sale


class ProductDetailSerializer(ProductListSerializer):
    """
    Полное представление товара для карточки.
    """

    images = ProductImageSerializer(many=True, read_only=True)
    stocks = ProductStockSerializer(many=True, read_only=True)
    characteristics = ProductCharacteristicSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields: ClassVar[list[str]] = [
            *ProductListSerializer.Meta.fields,
            "name_full",
            "description",
            "production_time_days",
            "images",
            "stocks",
            "characteristics",
            "variants",
        ]

    def get_variants(self, obj: Product) -> list[dict[str, object]]:
        """
        Варианты того же товара (другие цвета/размеры) для переключателя.

        Если товар входит в группу — возвращаем все товары группы,
        включая текущий (фронт подсветит выбранный), отсортированные
        по id. Если группы нет (товар без вариантов) — пустой список.
        """
        group = obj.group
        if group is None:
            return []
        variants = group.variants.order_by("id")
        serialized = ProductVariantSerializer(
            variants,
            many=True,
            context=self.context,
        )
        return list(serialized.data)
