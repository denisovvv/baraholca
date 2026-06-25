from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Админка для кастомной модели User с авторизацией по телефону.
    """

    list_display = (
        "phone",
        "phone_verified",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "phone_verified")
    search_fields = ("phone", "first_name", "last_name", "email")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("phone", "phone_verified", "password")}),
        (_("Личные данные"), {"fields": ("first_name", "last_name", "email")}),
        (_("Соцсети"), {"fields": ("vk_id", "apple_id"), "classes": ("collapse",)}),
        (
            _("Права"),
            {
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
        (_("Важные даты"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone", "password1", "password2"),
            },
        ),
    )
