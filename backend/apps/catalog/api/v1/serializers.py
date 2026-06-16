"""
Сериализаторы для API каталога: категории, склады, товары.
"""

from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Product,
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
        source='parent.name',
        read_only=True,
        allow_null=True,
    )
    full_path = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'parent',
            'parent_name',
            'full_path',
            'order',
        ]

    def get_full_path(self, obj):
        return obj.get_full_path()

class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Категория с вложенными дочерними категориями (дерево).
    """

    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'order',
            'children',
        ]

    def get_children(self, obj):
        """
        Рекурсивно сериализует активные дочерние категории.
        """
        children = obj.children.filter(is_active=True).order_by('order', 'name')
        return CategoryTreeSerializer(children, many=True).data


# ============================================================================
# Warehouse
# ============================================================================

class WarehouseListSerializer(serializers.ModelSerializer):
    """
    Короткое представление склада для списков.
    """

    seller_name = serializers.CharField(
        source='seller.short_name',
        read_only=True,
    )
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            'id',
            'name',
            'seller_name',
            'address',
            'latitude',
            'longitude',
            'pickup_available',
        ]

    def get_latitude(self, obj):
        """Широта."""
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        """Долгота."""
        return obj.location.x if obj.location else None


class WarehouseDetailSerializer(WarehouseListSerializer):
    """
    Полное представление склада для карточки одного объекта.
    """

    class Meta(WarehouseListSerializer.Meta):
        fields = WarehouseListSerializer.Meta.fields + [
            'contact_phone',
            'working_hours',
        ]

class WarehouseNearbySerializer(WarehouseListSerializer):
    """
    Склад с расстоянием до точки покупателя.
    """

    distance_km = serializers.SerializerMethodField()

    class Meta(WarehouseListSerializer.Meta):
        fields = WarehouseListSerializer.Meta.fields + ['distance_km']

    def get_distance_km(self, obj):
        """
        Расстояние до склада в километрах, округлённое до 1 знака.
        """
        if hasattr(obj, 'distance') and obj.distance is not None:
            return round(obj.distance.km, 1)
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
        fields = [
            'id',
            'image_url',
            'order',
            'is_main',
        ]

    def get_image_url(self, obj):
        """Полный URL изображения с учётом домена."""
        request = self.context.get('request')
        if not obj.image:
            return None
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


# ============================================================================
# ProductStock
# ============================================================================

class ProductStockSerializer(serializers.ModelSerializer):
    """
    Остатки товара по складам.
    """

    warehouse_name = serializers.CharField(
        source='warehouse.name',
        read_only=True,
    )
    warehouse_address = serializers.CharField(
        source='warehouse.address',
        read_only=True,
    )
    available = serializers.SerializerMethodField()

    class Meta:
        model = ProductStock
        fields = [
            'warehouse_name',
            'warehouse_address',
            'available',
        ]

    def get_available(self, obj):
        return obj.available_quantity > 0


# ============================================================================
# Product
# ============================================================================

class ProductListSerializer(serializers.ModelSerializer):
    """
    Короткое представление товара для списков и каталога.
    """

    seller_name = serializers.CharField(
        source='seller.short_name',
        read_only=True,
    )
    category_name = serializers.CharField(
        source='category.name',
        read_only=True,
        allow_null=True,
    )
    main_image_url = serializers.SerializerMethodField()
    effective_price = serializers.DecimalField(
        source='get_effective_price',
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Product
        fields = [
            'id',
            'name_short',
            'seller_name',
            'category_name',
            'main_image_url',
            'base_price',
            'discount_price',
            'effective_price',
            'product_type',
        ]

    def get_main_image_url(self, obj):
        """
        URL главного фото товара.
        """
        main = obj.images.filter(is_main=True).first()
        if not main:
            main = obj.images.first()
        if not main:
            return None

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(main.image.url)
        return main.image.url


class ProductDetailSerializer(ProductListSerializer):
    """
    Полное представление товара для карточки.
    """

    images = ProductImageSerializer(many=True, read_only=True)
    stocks = ProductStockSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            'name_full',
            'description',
            'production_time_days',
            'images',
            'stocks',
        ]