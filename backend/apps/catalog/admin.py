from decimal import Decimal
from typing import Any, ClassVar

from django import forms
from django.contrib import admin, messages
from django.contrib.gis.admin import GISModelAdmin
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render

from apps.catalog.forms import ApplyDiscountForm, WorkingHoursFormField
from apps.catalog.models import Category, Product, ProductImage, ProductStock, Warehouse


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("get_full_path", "order", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    list_editable = ("order", "is_active")
    prepopulated_fields: ClassVar[dict[str, tuple[str, ...]]] = {"slug": ("name",)}
    autocomplete_fields = ("parent",)

    fieldsets = (
        (None, {"fields": ("name", "slug", "parent")}),
        ("Контент", {"fields": ("description", "image")}),
        ("Настройки", {"fields": ("order", "is_active")}),
        ("Системное", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at")

    def get_full_path(self, obj: Category) -> str:
        return obj.get_full_path()

    get_full_path.short_description = "Категория"
    get_full_path.admin_order_field = "name"

    def save_model(
        self,
        request: HttpRequest,
        obj: Category,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
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

    class Media:
        css: ClassVar[dict[str, tuple[str, ...]]] = {"all": ("admin/css/gis_map_fix.css",)}

    # Начальный вид карты — центр между Воронежем и Белгородом
    def formfield_for_dbfield(
        self,
        db_field: models.Field,
        request: HttpRequest,
        **kwargs: Any,
    ) -> forms.Field | None:
        """
        Подменяем стандартное JSON-поле working_hours на наш кастомный виджет.
        """
        if db_field.name == "working_hours":
            return WorkingHoursFormField(label=db_field.verbose_name, required=False)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    gis_widget_kwargs: ClassVar[dict[str, dict[str, float | int]]] = {
        "attrs": {
            "default_lat": 51.1,
            "default_lon": 37.9,
            "default_zoom": 8,
        },
    }

    list_display = ("name", "seller", "address", "pickup_available", "is_active", "created_at")
    search_fields = ("name", "address", "seller__name", "seller__short_name")
    autocomplete_fields = ("seller",)
    readonly_fields = ("created_at", "updated_at", "uuid_1c")

    fieldsets = (
        (None, {"fields": ("seller", "name", "address", "is_active")}),
        (
            "Местоположение",
            {
                "fields": ("location", "delivery_area"),
                "description": "Точка центра склада обязательна. Полигон зоны доставки можно нарисовать позже.",
            },
        ),
        ("Настройки", {"fields": ("pickup_available", "working_hours", "contact_phone")}),
        (
            "Системное",
            {"fields": ("uuid_1c", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class ProductImageInline(admin.TabularInline):
    """
    Инлайн для отображения фотографий товара прямо на странице товара.
    """

    model = ProductImage
    extra = 1
    fields = ("image", "is_main", "order")


class ProductStockInline(admin.TabularInline):
    """
    Инлайн для отображения остатков товара на складах прямо на странице товара.
    Показывает quantity, reserved_quantity и available_quantity.
    """

    model = ProductStock
    extra = 0
    fields = (
        "warehouse",
        "quantity",
        "reserved_quantity",
        "available_quantity_display",
        "updated_at",
    )
    readonly_fields = ("available_quantity_display", "updated_at")
    autocomplete_fields = ("warehouse",)

    def available_quantity_display(self, obj: ProductStock) -> str:
        if obj.pk is None:
            return "—"
        return f"{obj.available_quantity} шт."

    available_quantity_display.short_description = "Доступно"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Админка для товаров.

    Большинство данных приходит из 1С и не редактируется вручную:
    название, базовая цена, флаг доступности, UUID.

    В админке управляются: категория, тип товара, скидочная цена,
    флаг is_active, время изготовления (для made_to_order).
    """

    inlines: ClassVar[list[type[admin.TabularInline]]] = [ProductImageInline, ProductStockInline]

    list_display = (
        "name_short",
        "seller",
        "category",
        "product_type",
        "get_effective_price_display",
        "is_available_for_sale",
        "is_active",
        "created_at",
    )
    list_filter = (
        "seller",
        "category",
        "product_type",
        "is_available_for_sale",
        "is_active",
    )
    search_fields = (
        "name_short",
        "name_full",
        "description",
        "uuid_1c",
    )
    list_editable = ("is_active",)
    autocomplete_fields = ("seller", "category")
    readonly_fields = (
        "uuid_1c",
        "created_at",
        "updated_at",
        "synced_at",
        "get_effective_price_display",
    )

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "seller",
                    "category",
                    "name_short",
                    "name_full",
                    "description",
                )
            },
        ),
        (
            "Тип и наличие",
            {
                "fields": (
                    "product_type",
                    "production_time_days",
                    "is_available_for_sale",
                    "is_active",
                )
            },
        ),
        (
            "Цены",
            {
                "fields": (
                    "base_price",
                    "discount_price",
                    "get_effective_price_display",
                )
            },
        ),
        (
            "Системное",
            {
                "fields": (
                    "uuid_1c",
                    "created_at",
                    "updated_at",
                    "synced_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_effective_price_display(self, obj: Product) -> str:
        """
        Отображение актуальной цены в списке и в форме.
        """
        if obj.pk is None:
            return "—"
        price = obj.get_effective_price()
        if obj.discount_price is not None:
            return f"{price} ₽ (со скидкой)"
        return f"{price} ₽"

    get_effective_price_display.short_description = "Актуальная цена"

    def save_model(
        self,
        request: HttpRequest,
        obj: Product,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        """
        Перед сохранением вызываем full_clean(), чтобы сработала валидация модели.
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)

    actions: ClassVar[list[str]] = ["apply_discount_action"]

    def apply_discount_action(
        self,
        request: HttpRequest,
        queryset: QuerySet[Product],
    ) -> HttpResponse:
        """
        Admin action для массового применения скидки к выбранным товарам.
        """
        # Получаем ID выбранных товаров
        selected_ids = list(queryset.values_list("id", flat=True))

        # Если пользователь только что отправил форму — применяем скидку
        if "apply" in request.POST:
            form = ApplyDiscountForm(request.POST)
            if form.is_valid():
                discount_type = form.cleaned_data["discount_type"]
                percent_value = form.cleaned_data.get("percent_value")
                fixed_value = form.cleaned_data.get("fixed_value")

                applied_count = 0
                skipped_count = 0

                for product in queryset:
                    base_price = product.base_price

                    # Считаем новую цену
                    if discount_type == ApplyDiscountForm.DISCOUNT_TYPE_PERCENT:
                        discount_amount = base_price * percent_value / Decimal("100")
                        new_price = base_price - discount_amount
                    else:
                        new_price = base_price - fixed_value

                    # Округляем до копеек
                    new_price = new_price.quantize(Decimal("0.01"))

                    # Валидация: цена не должна быть отрицательной или равной базовой
                    if new_price <= 0:
                        skipped_count += 1
                        continue
                    if new_price >= base_price:
                        skipped_count += 1
                        continue

                    product.discount_price = new_price
                    product.save()
                    applied_count += 1

                if applied_count:
                    self.message_user(
                        request,
                        f"Скидка применена к {applied_count} товарам.",
                        messages.SUCCESS,
                    )
                if skipped_count:
                    self.message_user(
                        request,
                        f"Пропущено {skipped_count} товаров (скидка слишком большая или цена не уменьшается).",
                        messages.WARNING,
                    )

                return HttpResponseRedirect(request.get_full_path())
        else:
            form = ApplyDiscountForm()

        # Готовим предпросмотр для формы
        preview = []
        for product in queryset[:5]:  # показываем первые 5 для предпросмотра
            preview.append(
                {
                    "name": product.name_short,
                    "base_price": product.base_price,
                    "current_discount": product.discount_price,
                }
            )

        context = {
            "title": "Применить скидку к товарам",
            "products_count": queryset.count(),
            "preview": preview,
            "form": form,
            "selected_ids": selected_ids,
        }
        return render(request, "admin/catalog/apply_discount.html", context)

    apply_discount_action.short_description = "Применить скидку к выбранным товарам"


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    """
    Админка для остатков на складах.
    Основной просмотр — на странице товара (инлайн).
    Этот раздел — для общего обзора и фильтрации остатков по складам.
    """

    list_display = (
        "product",
        "warehouse",
        "quantity",
        "reserved_quantity",
        "available_quantity_display",
        "updated_at",
    )
    list_filter = ("warehouse", "product__seller", "product__category")
    search_fields = ("product__name_short", "product__uuid_1c", "warehouse__name")
    autocomplete_fields = ("product", "warehouse")
    readonly_fields = ("updated_at",)

    def available_quantity_display(self, obj: ProductStock) -> str:
        return f"{obj.available_quantity} шт."

    available_quantity_display.short_description = "Доступно"

    def save_model(
        self,
        request: HttpRequest,
        obj: ProductStock,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        """
        Валидация на сохранение (проверка отрицательных значений и т.д.).
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)
