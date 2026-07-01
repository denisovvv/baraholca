"""
Админка приложения cart.

Регистрирует:
- Favorite — простая таблица «пользователь → товар».
- Cart — корзина с inline CartItem (позиции показываются внутри).
- CartItem — тоже отдельно, чтобы можно было фильтровать позиции
  всех пользователей по конкретному товару (полезно для аналитики
  «сколько раз этот товар лежит в корзинах»).

get_items_count в CartAdmin использует аннотацию через get_queryset,
чтобы не делать N+1 SQL для подсчёта позиций.
"""

from typing import ClassVar, cast

from django.contrib import admin
from django.db import models
from django.http import HttpRequest

from apps.cart.models import Cart, CartItem, Favorite


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


class CartItemInline(admin.TabularInline):
    """
    Позиции корзины внутри страницы Cart.

    Табличный вид — компактный, удобно смотреть все позиции сразу.
    extra=0 отключает пустые строки для новых позиций: в отладочной
    админке добавлять позицию вручную нужно редко.
    """

    model = CartItem
    extra = 0
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("product",)
    readonly_fields: ClassVar[tuple[str, ...]] = ("added_at",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Админ-панель для корзин.

    Список показывает: пользователь, число позиций (через аннотацию —
    один SQL для всех корзин), даты. Inline с CartItem внутри позволяет
    редактировать позиции прямо со страницы корзины.
    """

    list_display: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "user",
        "get_items_count",
        "created_at",
        "updated_at",
    )
    list_filter: ClassVar[tuple[str, ...]] = ("created_at", "updated_at")
    search_fields: ClassVar[tuple[str, ...]] = (
        "user__phone",
        "user__first_name",
        "user__last_name",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = ("created_at", "updated_at")
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("user",)
    ordering: ClassVar[tuple[str, ...]] = ("-updated_at",)
    inlines: ClassVar[list[type[admin.TabularInline]]] = [CartItemInline]  # type: ignore[assignment]

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[Cart]:
        """
        Аннотируем queryset количеством позиций, чтобы избежать
        N+1 SQL при рендере списка корзин.
        """
        return super().get_queryset(request).annotate(_items_count=models.Count("items"))  # type: ignore[no-any-return]

    @admin.display(description="Позиций", ordering="_items_count")
    def get_items_count(self, obj: Cart) -> int:
        """
        Число позиций в корзине.

        Берётся из аннотированного queryset (см. get_queryset).
        ordering="_items_count" позволяет сортировать список
        корзин по числу позиций кликом на заголовок колонки.
        """
        return cast(int, obj._items_count)  # type: ignore[attr-defined]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Отдельная админка для позиций корзины.

    Полезно для аналитики: "сколько корзин содержат этот товар",
    "какие товары чаще кладут в корзину" — можно фильтровать
    и группировать через админский поиск.
    """

    list_display: ClassVar[tuple[str, ...]] = ("cart", "product", "quantity", "added_at")  # type: ignore[misc]
    list_filter: ClassVar[tuple[str, ...]] = ("added_at",)
    search_fields: ClassVar[tuple[str, ...]] = (
        "cart__user__phone",
        "product__name_short",
        "product__uuid_1c",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = ("added_at",)
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("cart", "product")
    ordering: ClassVar[tuple[str, ...]] = ("-added_at",)
