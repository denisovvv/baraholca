from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from apps.catalog.models import Category, Product, ProductImage, ProductStock, Warehouse


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('get_full_path', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    list_editable = ('order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('parent',)

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'parent')
        }),
        ('Контент', {
            'fields': ('description', 'image')
        }),
        ('Настройки', {
            'fields': ('order', 'is_active')
        }),
        ('Системное', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def get_full_path(self, obj):
        return obj.get_full_path()
    get_full_path.short_description = 'Категория'
    get_full_path.admin_order_field = 'name'

    def save_model(self, request, obj, form, change):
        """
        Перед сохранением вызываем full_clean(), чтобы сработала валидация модели.
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)

@admin.register(Warehouse)


class WarehouseAdmin(GISModelAdmin):
    """
    Админка для склада с поддержкой гео-полей.
    Используется встроенная GISModelAdmin Django с картой OpenStreetMap.
    """
# Начальный вид карты — центр между Воронежем и Белгородом
    gis_widget_kwargs = {
        'attrs': {
            'default_lat': 51.1,
            'default_lon': 37.9,
            'default_zoom': 8,
        },
    }

    list_display = ('name', 'seller', 'address', 'pickup_available', 'is_active', 'created_at')
    search_fields = ('name', 'address', 'seller__name', 'seller__short_name')
    autocomplete_fields = ('seller',)
    readonly_fields = ('created_at', 'updated_at', 'uuid_1c')

    fieldsets = (
        (None, {
            'fields': ('seller', 'name', 'address', 'is_active')
        }),
        ('Местоположение', {
            'fields': ('location', 'delivery_area'),
            'description': 'Точка центра склада обязательна. Полигон зоны доставки можно нарисовать позже.'
        }),
        ('Настройки', {
            'fields': ('pickup_available', 'working_hours', 'contact_phone')
        }),
        ('Системное', {
            'fields': ('uuid_1c', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class ProductImageInline(admin.TabularInline):
    """
    Инлайн для отображения фотографий товара прямо на странице товара.
    """
    model = ProductImage
    extra = 1
    fields = ('image', 'is_main', 'order')

class ProductStockInline(admin.TabularInline):
    """
    Инлайн для отображения остатков товара на складах прямо на странице товара.
    Показывает quantity, reserved_quantity и available_quantity.
    """
    model = ProductStock
    extra = 0
    fields = ('warehouse', 'quantity', 'reserved_quantity', 'available_quantity_display', 'updated_at')
    readonly_fields = ('available_quantity_display', 'updated_at')
    autocomplete_fields = ('warehouse',)

    def available_quantity_display(self, obj):
        if obj.pk is None:
            return '—'
        return f'{obj.available_quantity} шт.'

    available_quantity_display.short_description = 'Доступно'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Админка для товаров.

    Большинство данных приходит из 1С и не редактируется вручную:
    название, базовая цена, флаг доступности, UUID.

    В админке управляются: категория, тип товара, скидочная цена,
    флаг is_active, время изготовления (для made_to_order).
    """

    inlines = [ProductImageInline, ProductStockInline]

    list_display = (
        'name_short',
        'seller',
        'category',
        'product_type',
        'get_effective_price_display',
        'is_available_for_sale',
        'is_active',
        'created_at',
    )
    list_filter = (
        'seller',
        'category',
        'product_type',
        'is_available_for_sale',
        'is_active',
    )
    search_fields = (
        'name_short',
        'name_full',
        'description',
        'uuid_1c',
    )
    list_editable = ('is_active',)
    autocomplete_fields = ('seller', 'category')
    readonly_fields = (
        'uuid_1c',
        'created_at',
        'updated_at',
        'synced_at',
        'get_effective_price_display',
    )

    fieldsets = (
        ('Основное', {
            'fields': (
                'seller',
                'category',
                'name_short',
                'name_full',
                'description',
            )
        }),
        ('Тип и наличие', {
            'fields': (
                'product_type',
                'production_time_days',
                'is_available_for_sale',
                'is_active',
            )
        }),
        ('Цены', {
            'fields': (
                'base_price',
                'discount_price',
                'get_effective_price_display',
            )
        }),
        ('Системное', {
            'fields': (
                'uuid_1c',
                'created_at',
                'updated_at',
                'synced_at',
            ),
            'classes': ('collapse',),
        }),
    )

    def get_effective_price_display(self, obj):
        """
        Отображение актуальной цены в списке и в форме.
        """
        if obj.pk is None:
            return '—'
        price = obj.get_effective_price()
        if obj.discount_price is not None:
            return f'{price} ₽ (со скидкой)'
        return f'{price} ₽'

    get_effective_price_display.short_description = 'Актуальная цена'

    def save_model(self, request, obj, form, change):
        """
        Перед сохранением вызываем full_clean(), чтобы сработала валидация модели.
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    """
    Админка для остатков на складах.
    Основной просмотр — на странице товара (инлайн).
    Этот раздел — для общего обзора и фильтрации остатков по складам.
    """

    list_display = ('product', 'warehouse', 'quantity', 'reserved_quantity', 'available_quantity_display', 'updated_at')
    list_filter = ('warehouse', 'product__seller', 'product__category')
    search_fields = ('product__name_short', 'product__uuid_1c', 'warehouse__name')
    autocomplete_fields = ('product', 'warehouse')
    readonly_fields = ('updated_at',)

    def available_quantity_display(self, obj):
        return f'{obj.available_quantity} шт.'

    available_quantity_display.short_description = 'Доступно'

    def save_model(self, request, obj, form, change):
        """
        Валидация на сохранение (проверка отрицательных значений и т.д.).
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)
