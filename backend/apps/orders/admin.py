"""
Админка приложения orders.

OrderAdmin — заказ со всеми деталями. Fieldsets группируют 25+ полей
по смыслу (идентификация, статус, доставка, оплата, суммы, 1С, даты).
Inline с OrderItem и OrderStatusHistory показывают позиции и историю
прямо на странице заказа.

OrderItemAdmin регистрируется отдельно для аналитики: фильтровать
позиции по продукту, продавцу, заказу — полезно на разработке.

OrderStatusHistoryAdmin — тоже отдельно, для аудита действий поддержки:
кто когда менял статус заказа. Все поля readonly — это лог.

select_related в get_queryset избегает N+1: без него список заказов
делает по три SQL на каждую строку (user, seller, warehouse).
"""

from typing import ClassVar

from django.contrib import admin
from django.db import models
from django.http import HttpRequest

from apps.orders.models import (
    Order,
    OrderItem,
    OrderStatusHistory,
    PaymentStatusHistory,
)


class OrderItemInline(admin.TabularInline):
    """
    Позиции заказа внутри страницы Order.

    Snapshot полей (product_name_snapshot, price, sum) нельзя менять
    после создания — задают финансовую истину заказа. Показываем как
    readonly.
    """

    model = OrderItem
    extra = 0
    can_delete = False
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("product",)
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "product_name_snapshot",
        "product_uuid_1c",
        "quantity",
        "price",
        "sum",
    )
    show_change_link = True


class OrderStatusHistoryInline(admin.TabularInline):
    """
    История статусов внутри страницы Order.

    Аудитный лог, никаких изменений через админку — только чтение.
    can_delete=False, extra=0, все поля readonly.
    """

    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "status_from",
        "status_to",
        "changed_by",
        "changed_at",
        "comment",
        "is_automatic",
    )
    show_change_link = True

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: Order | None = None,
    ) -> bool:
        """Запретить создание истории через админку — только автоматически."""
        return False


class PaymentStatusHistoryInline(admin.TabularInline):
    """
    История оплаты внутри страницы Order.

    Симметрична OrderStatusHistoryInline, но для оси оплаты.
    Аудитный лог, только чтение.
    """

    model = PaymentStatusHistory
    extra = 0
    can_delete = False
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "status_from",
        "status_to",
        "changed_by",
        "changed_at",
        "comment",
        "is_automatic",
    )
    show_change_link = True

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: Order | None = None,
    ) -> bool:
        """Запретить создание истории оплаты через админку."""
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Админ-панель заказа.

    Список показывает ключевую информацию для быстрого сканирования:
    номер, покупатель, продавец, статусы, сумма, дата. Фильтры —
    по статусам и датам. Поиск — по номеру и данным получателя.

    Fieldsets группируют 25+ полей заказа для читаемости страницы
    редактирования. Inline OrderItem и OrderStatusHistory показывают
    позиции и историю прямо здесь.
    """

    list_display: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "number",
        "user",
        "seller",
        "status",
        "payment_status",
        "total",
        "created_at",
    )
    list_filter: ClassVar[tuple[str, ...]] = (
        "status",
        "payment_status",
        "delivery_method",
        "payment_method",
        "seller",
        "created_at",
    )
    search_fields: ClassVar[tuple[str, ...]] = (
        "number",
        "user__phone",
        "user__first_name",
        "user__last_name",
        "recipient_name",
        "recipient_phone",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "uuid",
        "number",
        "created_at",
        "updated_at",
        "paid_at",
        "shipped_at",
        "delivered_at",
        "cancelled_at",
        "docnum_1c",
        "synced_at_1c",
    )
    autocomplete_fields: ClassVar[tuple[str, ...]] = (
        "user",
        "seller",
        "warehouse",
    )
    ordering: ClassVar[tuple[str, ...]] = ("-created_at",)
    inlines: ClassVar[list[type[admin.TabularInline]]] = [  # type: ignore[assignment]
        OrderItemInline,
        OrderStatusHistoryInline,
        PaymentStatusHistoryInline,
    ]

    fieldsets: ClassVar[tuple[tuple[str, dict[str, tuple[str, ...]]], ...]] = (  # type: ignore[assignment]
        (
            "Идентификация",
            {"fields": ("uuid", "number", "user", "seller", "warehouse")},
        ),
        (
            "Статусы",
            {"fields": ("status", "payment_status")},
        ),
        (
            "Доставка",
            {
                "fields": (
                    "delivery_method",
                    "delivery_address",
                    "delivery_latitude",
                    "delivery_longitude",
                    "delivery_comment",
                    "recipient_name",
                    "recipient_phone",
                ),
            },
        ),
        (
            "Оплата и суммы",
            {"fields": ("payment_method", "subtotal", "delivery_cost", "total")},
        ),
        (
            "Комментарий",
            {"fields": ("comment",)},
        ),
        (
            "Интеграция с 1С",
            {"fields": ("docnum_1c", "synced_at_1c"), "classes": ("collapse",)},
        ),
        (
            "Даты",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "paid_at",
                    "shipped_at",
                    "delivered_at",
                    "cancelled_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[Order]:
        """
        Оптимизация N+1: список заказов подтягивает user/seller/warehouse
        одним JOIN-запросом вместо трёх на каждую строку.
        """
        return (
            super()
            .get_queryset(request)
            .select_related(
                "user",
                "seller",
                "warehouse",
            )
        )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """
    Отдельная админка для позиций заказа.

    Полезно для аналитики: фильтровать по продукту, продавцу.
    Например, "все продажи товара X" или "сколько позиций у продавца Y".
    """

    list_display: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "order",
        "product_name_snapshot",
        "quantity",
        "price",
        "sum",
    )
    list_filter: ClassVar[tuple[str, ...]] = ("order__seller",)
    search_fields: ClassVar[tuple[str, ...]] = (
        "order__number",
        "product_name_snapshot",
        "product__name_short",
        "product__uuid_1c",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "product_name_snapshot",
        "product_uuid_1c",
        "quantity",
        "price",
        "sum",
    )
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("order", "product")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    """
    Аудитный лог смены статусов заказов.

    Все поля readonly — историю нельзя редактировать.
    Полезно для разбора спорных ситуаций: кто когда что менял.
    """

    list_display: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "order",
        "status_from",
        "status_to",
        "changed_by",
        "changed_at",
        "is_automatic",
    )
    list_filter: ClassVar[tuple[str, ...]] = (
        "status_to",
        "is_automatic",
        "changed_at",
    )
    search_fields: ClassVar[tuple[str, ...]] = (
        "order__number",
        "changed_by__phone",
        "comment",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "order",
        "status_from",
        "status_to",
        "changed_by",
        "changed_at",
        "comment",
        "is_automatic",
    )
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("order", "changed_by")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Записи истории создаются только автоматически, не через админку."""
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: OrderStatusHistory | None = None,
    ) -> bool:
        """Аудитный лог не редактируется."""
        return False


@admin.register(PaymentStatusHistory)
class PaymentStatusHistoryAdmin(admin.ModelAdmin):
    """
    Аудитный лог смены статусов оплаты.

    Симметричен OrderStatusHistoryAdmin, но для оси оплаты.
    Все поля readonly — историю нельзя редактировать.
    """

    list_display: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "order",
        "status_from",
        "status_to",
        "changed_by",
        "changed_at",
        "is_automatic",
    )
    list_filter: ClassVar[tuple[str, ...]] = (
        "status_to",
        "is_automatic",
        "changed_at",
    )
    search_fields: ClassVar[tuple[str, ...]] = (
        "order__number",
        "changed_by__phone",
        "comment",
    )
    readonly_fields: ClassVar[tuple[str, ...]] = (
        "order",
        "status_from",
        "status_to",
        "changed_by",
        "changed_at",
        "comment",
        "is_automatic",
    )
    autocomplete_fields: ClassVar[tuple[str, ...]] = ("order", "changed_by")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Записи истории создаются только автоматически, не через админку."""
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: PaymentStatusHistory | None = None,
    ) -> bool:
        """Аудитный лог не редактируется."""
        return False
