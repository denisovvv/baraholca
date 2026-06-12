"""
Сериализаторы для API каталога: категории, склады, товары.

Используется паттерн «List → Detail» — короткий сериализатор для списков
и расширенный для карточек отдельного объекта.
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

    Поля parent_name и full_path — вычисляемые, помогают
    мобильному приложению показывать иерархию без отдельных запросов.
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
        """
        Возвращает полный путь категории, например: 'Посуда → Кружки'.
        Использует метод модели get_full_path().
        """
        return obj.get_full_path()


# ============================================================================
# Warehouse
# ============================================================================

class WarehouseListSerializer(serializers.ModelSerializer):
    """
    Короткое представление склада для списков.

    Используется когда показываем десятки складов на карте.
    Только самое необходимое: имя, адрес, координаты.
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
        """Широта. PostGIS Point: y = latitude."""
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        """Долгота. PostGIS Point: x = longitude."""
        return obj.location.x if obj.location else None


class WarehouseDetailSerializer(WarehouseListSerializer):
    """
    Полное представление склада для карточки одного объекта.

    Наследует базовые поля от List и добавляет контактный телефон
    и часы работы.

    Поле delivery_area (полигон зоны доставки) НЕ включаем — мобильному
    приложению полигон не нужен, он используется только сервером
    для расчёта зоны при оформлении заказа.
    """

    class Meta(WarehouseListSerializer.Meta):
        fields = WarehouseListSerializer.Meta.fields + [
            'contact_phone',
            'working_hours',
        ]

class WarehouseNearbySerializer(WarehouseListSerializer):
    """
    Склад с расстоянием до точки покупателя.

    Используется в endpoint поиска ближайших складов.
    Поле distance_km добавляется аннотацией в queryset (PostGIS).
    """

    distance_km = serializers.SerializerMethodField()

    class Meta(WarehouseListSerializer.Meta):
        fields = WarehouseListSerializer.Meta.fields + ['distance_km']

    def get_distance_km(self, obj):
        """
        Расстояние до склада в километрах, округлённое до 1 знака.

        obj.distance — это аннотированное PostGIS-поле (объект Distance).
        Атрибут .km даёт значение в километрах.
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

    Возвращает абсолютный URL изображения вместе с относительным путём.
    Абсолютный URL формируется из request — для разработки получится
    http://127.0.0.1:8000/..., для прода — https://api.baraxolka.ru/...
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

    ВАЖНО: точное количество (quantity) НЕ возвращается клиенту —
    это коммерческая информация. Возвращаем только флаг наличия.
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
        """
        Доступно ли для покупки.
        Использует свойство модели available_quantity = quantity - reserved.
        """
        return obj.available_quantity > 0


# ============================================================================
# Product
# ============================================================================

class ProductListSerializer(serializers.ModelSerializer):
    """
    Короткое представление товара для списков и каталога.

    Включает главное фото (одно) и эффективную цену (со скидкой если есть).
    Подробности — в ProductDetailSerializer.
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
        URL главного фото товара. Если главного нет — берём первое.
        Возвращает None если фото вообще нет.
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

    Включает все фото, остатки по складам, описание,
    время изготовления (для товаров под заказ).
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