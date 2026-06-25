from django.contrib import admin

from apps.sellers.models import Seller, SellerStaff


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


@admin.register(SellerStaff)
class SellerStaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'seller', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'seller')
    search_fields = ('user__phone', 'user__first_name', 'user__last_name', 'seller__name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user', 'seller')

    fieldsets = (
        (None, {
            'fields': ('user', 'seller', 'role', 'is_active')
        }),
        ('Системное', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
