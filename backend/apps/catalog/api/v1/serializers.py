"""
Сериализаторы для API каталога: категории, склады, товары.

Используется паттерн «List → Detail» — короткий сериализатор для списков
и расширенный для карточек отдельного объекта.
"""

from rest_framework import serializers

from apps.catalog.models import Category, Warehouse


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