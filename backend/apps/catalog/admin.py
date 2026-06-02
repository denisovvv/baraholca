from django.contrib import admin

from apps.catalog.models import Category


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