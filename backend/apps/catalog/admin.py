from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from apps.catalog.models import Category, Warehouse


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