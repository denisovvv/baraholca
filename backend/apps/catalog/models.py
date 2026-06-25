from decimal import Decimal
from typing import Any, ClassVar

from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """
    Категория товаров. Поддерживает вложенность (категория → подкатегория).
    Максимальная глубина — 3 уровня.

    Категории создаются и редактируются в админке приложения.
    Из 1С не синхронизируются.
    """

    name = models.CharField(max_length=100, verbose_name="Название")
    slug = models.SlugField(
        max_length=120,
        unique=True,
        verbose_name="URL-идентификатор",
        help_text="Заполнится автоматически, если оставить пустым",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    image = models.ImageField(upload_to="categories/", blank=True, verbose_name="Изображение")
    order = models.IntegerField(
        default=0,
        verbose_name="Порядок сортировки",
        help_text="Чем меньше число, тем выше в списке",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна",
        help_text="Если выключено — категория и её товары не отображаются в каталоге",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering: ClassVar[list[str]] = ["order", "name"]

    def __str__(self) -> str:
        return self.get_full_path()

    def save(
        self,
        *args: Any,  # noqa: ANN401  # Django Model.save() принимает произвольные позиционные аргументы
        **kwargs: Any,  # noqa: ANN401  # Django Model.save() принимает force_insert, using, update_fields и т.п.
    ) -> None:
        # Автогенерация slug, если не заполнен
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def get_full_path(self) -> str:
        """
        Возвращает полный путь категории через все родительские.
        Например: 'Одежда / Мужская / Куртки'
        """
        if self.parent:
            return f"{self.parent.get_full_path()} / {self.name}"
        return self.name

    def get_level(self) -> int:
        """
        Возвращает уровень вложенности категории (0 для корневых).
        """
        if self.parent:
            return self.parent.get_level() + 1
        return 0

    def clean(self) -> None:
        """
        Валидация на уровне модели:
        - Запрещаем глубину вложенности больше 3 уровней
        - Запрещаем категории быть собственным родителем (циклы)
        """
        # Проверка циклов — категория не может быть родителем самой себе
        if self.parent and self.parent == self:
            raise ValidationError({"parent": "Категория не может быть родителем самой себе"})

        # Проверка глубины — максимум 3 уровня (0, 1, 2)
        if self.parent:
            # get_level() считает от 0 — если у родителя level=2, то у нас будет level=3, что уже слишком
            if self.parent.get_level() >= 2:
                raise ValidationError(
                    {"parent": "Превышена максимальная глубина вложенности (3 уровня)"}
                )

        # Проверка цикла через родителей — не допускаем, чтобы категория была своим прапредком
        if self.parent and self.pk:
            parent = self.parent
            while parent:
                if parent.pk == self.pk:
                    raise ValidationError(
                        {"parent": "Обнаружен цикл — категория не может быть потомком самой себя"}
                    )
                parent = parent.parent


class Warehouse(models.Model):
    """
    Склад / точка продавца.

    UUID склада приходит из 1С. Координаты центра и полигон зоны доставки
    ведутся в админке приложения.
    """

    uuid_1c = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        verbose_name="UUID в 1С",
        help_text="Идентификатор склада в системе 1С",
    )
    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.CASCADE,
        related_name="warehouses",
        verbose_name="Продавец",
    )
    name = models.CharField(
        max_length=150, verbose_name="Название", help_text="Например: «Склад на Ленина, 5»"
    )
    address = models.CharField(max_length=500, verbose_name="Адрес")

    # Геоданные — центр склада (для отображения на карте)
    location = gis_models.PointField(
        verbose_name="Координаты центра",
        help_text="Точка на карте, где расположен склад",
        srid=4326,
    )

    # Геоданные — зона доставки (полигон)
    delivery_area = gis_models.PolygonField(
        null=True,
        blank=True,
        verbose_name="Зона доставки",
        help_text="Полигон территории, на которую этот склад доставляет курьером",
        srid=4326,
    )

    pickup_available = models.BooleanField(
        default=True,
        verbose_name="Доступен самовывоз",
        help_text="Может ли покупатель забрать заказ с этого склада",
    )

    working_hours = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Часы работы",
        help_text="Часы работы по дням недели в формате JSON",
    )

    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Контактный телефон",
        help_text="Телефон склада для покупателей при самовывозе",
    )

    is_active = models.BooleanField(default=True, verbose_name="Активен")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")

    class Meta:
        verbose_name = "Склад"
        verbose_name_plural = "Склады"
        ordering: ClassVar[list[str]] = ["seller__name", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.seller.short_name or self.seller.name})"


class Product(models.Model):
    """
    Товар. Главная модель каталога.

    Основные данные приходят из 1С: название, базовая цена, остатки.
    В админке управляются: фото, скидки, флаг доступности на нашей стороне.
    """

    # Типы товаров
    TYPE_STOCK = "stock"
    TYPE_MADE_TO_ORDER = "made_to_order"

    TYPE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (TYPE_STOCK, "Со склада"),
        (TYPE_MADE_TO_ORDER, "Под заказ (3D-печать)"),
    ]

    # Идентификатор из 1С
    uuid_1c = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        verbose_name="UUID в 1С",
        help_text="Идентификатор товара в системе 1С (заполняется автоматически)",
    )

    # Названия
    name_short = models.CharField(
        max_length=255, verbose_name="Название краткое", help_text="Для списков, каталога"
    )
    name_full = models.CharField(
        max_length=500, blank=True, verbose_name="Название полное", help_text="Для карточки товара"
    )
    description = models.TextField(blank=True, verbose_name="Описание")

    # Связи
    seller = models.ForeignKey(
        "sellers.Seller", on_delete=models.PROTECT, related_name="products", verbose_name="Продавец"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Категория",
    )

    # Тип товара
    product_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_STOCK, verbose_name="Тип товара"
    )

    # Цены
    base_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Базовая цена", help_text="Цена из 1С (рубли)"
    )
    discount_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Скидочная цена",
        help_text="Если задана — используется вместо базовой цены",
    )

    # Флаги
    is_available_for_sale = models.BooleanField(
        default=True,
        verbose_name="Доступен к продаже (1С)",
        help_text="Управляется из 1С: глобальный флаг доступности товара",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен в системе",
        help_text="Управляется в админке: можно скрыть товар, не меняя данные в 1С",
    )

    # Для товаров под заказ
    production_time_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Время изготовления (дней)",
        help_text="Только для товаров под заказ",
    )

    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")
    synced_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Последняя синхронизация с 1С"
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["seller", "is_active"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_available_for_sale", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name_short

    def get_effective_price(self) -> Decimal:
        """
        Возвращает актуальную цену для покупателя.
        Если задана скидочная — её, иначе базовую.
        """
        if self.discount_price is not None:
            return self.discount_price
        return self.base_price

    def is_visible_in_catalog(self) -> bool:
        """
        Проверяет, виден ли товар в каталоге для покупателей.
        """
        return self.is_active and self.is_available_for_sale and self.seller.is_active

    def has_stock(self) -> bool:
        """
        Проверяет, есть ли товар в наличии хотя бы на одном складе.
        Для товаров «под заказ» всегда True (они не имеют остатков).
        """
        if self.product_type == self.TYPE_MADE_TO_ORDER:
            return True

        return self.stocks.filter(quantity__gt=models.F("reserved_quantity")).exists()

    def clean(self) -> None:
        """
        Валидация бизнес-логики:
        - У товара «под заказ» обязательно должно быть время изготовления
        - Скидочная цена должна быть меньше базовой (иначе нет смысла)
        """
        if self.product_type == self.TYPE_MADE_TO_ORDER:
            if not self.production_time_days:
                raise ValidationError(
                    {
                        "production_time_days": "Для товаров под заказ обязательно указать время изготовления"
                    }
                )

        if self.discount_price is not None and self.base_price is not None:
            if self.discount_price >= self.base_price:
                raise ValidationError(
                    {"discount_price": "Скидочная цена должна быть меньше базовой"}
                )


class ProductImage(models.Model):
    """
    Фотография товара.
    У товара может быть несколько фото. У одного из них должен быть флаг is_main=True.
    """

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images", verbose_name="Товар"
    )
    image = models.ImageField(upload_to="products/", verbose_name="Изображение")
    order = models.IntegerField(
        default=0,
        verbose_name="Порядок сортировки",
        help_text="Чем меньше число, тем раньше в галерее",
    )
    is_main = models.BooleanField(
        default=False,
        verbose_name="Главное фото",
        help_text="Используется в каталоге как обложка товара",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Фотография товара"
        verbose_name_plural = "Фотографии товаров"
        ordering: ClassVar[list[str]] = ["-is_main", "order", "created_at"]

    def __str__(self) -> str:
        return f"Фото {self.product.name_short} ({'главное' if self.is_main else 'доп.'})"

    def save(
        self,
        *args: Any,  # noqa: ANN401  # Django Model.save() принимает произвольные позиционные аргументы
        **kwargs: Any,  # noqa: ANN401  # Django Model.save() принимает force_insert, using, update_fields и т.п.
    ) -> None:
        """
        Если это фото отмечается как главное — сбрасываем флаг у всех остальных фото товара.
        Это гарантирует, что у одного товара только одно главное фото.
        """
        if self.is_main:
            # Снимаем флаг у всех других фото этого товара
            ProductImage.objects.filter(product=self.product, is_main=True).exclude(
                pk=self.pk
            ).update(is_main=False)
        super().save(*args, **kwargs)


class ProductStock(models.Model):
    """
    Остаток товара на конкретном складе.

    Связующая модель Product + Warehouse + количество.
    Данные приходят из 1С при синхронизации.
    """

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stocks", verbose_name="Товар"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stocks", verbose_name="Склад"
    )
    quantity = models.IntegerField(
        default=0,
        verbose_name="Количество",
        help_text="Остаток к продаже (за вычетом брака, приходит из 1С)",
    )
    reserved_quantity = models.IntegerField(
        default=0,
        verbose_name="В резервах",
        help_text="Количество в активных заказах (ещё не отгружено)",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")

    class Meta:
        verbose_name = "Остаток на складе"
        verbose_name_plural = "Остатки на складах"
        ordering: ClassVar[list[str]] = ["product", "warehouse"]
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["product", "warehouse"], name="unique_product_warehouse_stock"
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["warehouse"]),
            models.Index(fields=["product", "warehouse"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.name_short} → {self.warehouse.name}: {self.quantity} шт."

    @property
    def available_quantity(self) -> int:
        """
        Доступное к покупке количество.
        Это quantity минус то, что уже в активных резервах.
        """
        return max(0, self.quantity - self.reserved_quantity)

    def clean(self) -> None:
        """
        Валидация:
        - quantity не может быть отрицательным
        - reserved_quantity не может превышать quantity
        - reserved_quantity не может быть отрицательным
        """
        if self.quantity < 0:
            raise ValidationError({"quantity": "Количество не может быть отрицательным"})
        if self.reserved_quantity < 0:
            raise ValidationError({"reserved_quantity": "Резерв не может быть отрицательным"})
        if self.reserved_quantity > self.quantity:
            raise ValidationError(
                {
                    "reserved_quantity": f"Резерв ({self.reserved_quantity}) не может превышать остаток ({self.quantity})"
                }
            )
