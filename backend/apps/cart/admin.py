"""
Админка для приложения cart.

Пока содержит только Favorite. Cart и CartItem будут
добавлены отдельными шагами.
"""

from typing import ClassVar

from django.contrib import admin

from apps.cart.models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """
    Админ-панель для избранного.

    Для быстрой навигации и отладки: посмотреть кто что добавил,
    когда, проверить каскадные удаления при чистке пользователей.
    """

    list_display: ClassVar[tuple[str, ...]] = ("user", "product", "added_at")  # type: ignore[misc]
    list_filter: ClassVar[tuple[str, ...]] = ("added_at",)
    search_fields: ClassVar[tuple[str, ...]] = (
        "user__phone",
        "user__first_name",
        "user__last_name",
        "product__name_short",
        "product__uuid_1c",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = ("added_at",)
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("user", "product")
    ordering: ClassVar[tuple[str, ...]] = ("-added_at",)
