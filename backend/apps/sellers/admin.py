from django.contrib import admin

from apps.sellers.models import Seller


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'name', 'inn', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'short_name', 'inn', 'ogrnip')
    readonly_fields = ('created_at', 'updated_at', 'uuid_1c')

    fieldsets = (
        ('Юридические данные', {
            'fields': ('name', 'short_name', 'inn', 'ogrnip')
        }),
        ('Контакты', {
            'fields': ('contact_phone', 'contact_email')
        }),
        ('Управление', {
            'fields': ('admin_user', 'is_active')
        }),
        ('Системное', {
            'fields': ('uuid_1c', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )