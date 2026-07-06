"""
Админка приложения reviews.

ReviewAdmin — список отзывов с фильтром по рейтингу и поиском
по товару и пользователю. Модерация: staff может удалять
неуместные отзывы.
"""

from typing import ClassVar

from django.contrib import admin

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Админ-панель отзывов."""

    list_display: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "user",
        "product",
        "rating",
        "created_at",
    )
    list_filter: ClassVar[tuple[str, ...]] = (
        "rating",
        "created_at",
    )
    search_fields: ClassVar[tuple[str, ...]] = (
        "user__phone",
        "user__first_name",
        "user__last_name",
        "product__name_short",
        "text",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("user", "product")
