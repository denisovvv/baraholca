"""
Модели заказа: Order, OrderItem, OrderStatusHistory.

Order — заголовок заказа. Один заказ = один продавец (спека).
OrderItem — позиция заказа, snapshot цены и названия в момент заказа.
OrderStatusHistory — аудитный лог смены статусов.

on_delete=PROTECT на user/seller/warehouse: заказ переживает удаление
любой из этих сущностей. Если продавец уходит — деактивируется, а не удаляется.

Цены и названия в OrderItem — snapshot: изменение Product после заказа
не влияет на существующие заказы. Это гарантия честности перед клиентом.

Адрес доставки хранится встроенно в Order (delivery_address + координаты),
не как отдельная модель Address: адрес заказа — snapshot на момент оформления,
изменение основного адреса пользователя не должно затрагивать старые заказы.
"""

import uuid as uuid_pkg
from typing import Any, ClassVar

from django.conf import settings
from django.db import models

from apps.common.exceptions import ValidationError


class OrderStatus(models.TextChoices):
    """
    Статусы заказа согласно спеке (см. data-model.md → Слой 4).

    Разные цепочки для stock-товаров и made_to_order (3D-печать):
    stock:         pending_payment → paid → assembling → shipped → in_delivery → delivered
    made_to_order: pending_payment → paid → in_production → produced →
                    assembling → shipped → in_delivery → delivered

    cancelled возможен на любом этапе до shipped (для stock)
    или до in_production (для made_to_order).
    """

    PENDING_PAYMENT = "pending_payment", "Ожидает оплаты"
    PAID = "paid", "Оплачен"
    IN_PRODUCTION = "in_production", "В производстве"
    PRODUCED = "produced", "Изготовлен"
    ASSEMBLING = "assembling", "Собирается"
    SHIPPED = "shipped", "Отгружен"
    IN_DELIVERY = "in_delivery", "В доставке"
    DELIVERED = "delivered", "Доставлен"
    CANCELLED = "cancelled", "Отменён"


class PaymentStatus(models.TextChoices):
    """Статус оплаты (независим от Order.status)."""

    PENDING = "pending", "Ожидает оплаты"
    PAID = "paid", "Оплачен"
    REFUNDED = "refunded", "Возвращён"


class DeliveryMethod(models.TextChoices):
    """Способ получения заказа."""

    COURIER = "courier", "Курьер"
    PICKUP = "pickup", "Самовывоз"


class PaymentMethod(models.TextChoices):
    """Способ оплаты."""

    CARD_ONLINE = "card_online", "Картой онлайн"
    CASH_ON_DELIVERY = "cash_on_delivery", "Наличными при получении"


class Order(models.Model):
    """
    Заказ покупателя от одного продавца.

    Создаётся при checkout из корзины. Если в корзине товары от разных
    продавцов — создаётся несколько Order (один на каждого продавца).

    Номер (number) — человекочитаемый (BX-2026-000123), генерируется
    в момент создания. uuid — публичный идентификатор для API и 1С.
    """

    uuid = models.UUIDField(
        default=uuid_pkg.uuid4,
        unique=True,
        editable=False,
        verbose_name="UUID",
    )
    number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Номер заказа",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Покупатель",
    )
    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Продавец",
    )
    warehouse = models.ForeignKey(
        "catalog.Warehouse",
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Склад отгрузки",
    )

    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING_PAYMENT,
        verbose_name="Статус",
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        verbose_name="Статус оплаты",
    )

    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        verbose_name="Способ доставки",
    )
    delivery_address = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Адрес доставки",
    )
    delivery_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Широта адреса",
    )
    delivery_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Долгота адреса",
    )
    delivery_comment = models.TextField(
        blank=True,
        verbose_name="Комментарий курьеру",
    )
    recipient_name = models.CharField(
        max_length=150,
        verbose_name="ФИО получателя",
    )
    recipient_phone = models.CharField(
        max_length=20,
        verbose_name="Телефон получателя",
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        verbose_name="Способ оплаты",
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма товаров",
    )
    delivery_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Стоимость доставки",
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Итого",
    )

    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий к заказу",
    )

    docnum_1c = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Номер документа в 1С",
    )
    synced_at_1c = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Синхронизировано с 1С",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Оплачен")
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name="Отгружен")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Доставлен")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Отменён")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        return self.number

    def save(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """
        Валидация перехода статуса перед сохранением.

        Работает при любом save: сервис, админка, прямой save().
        Читает старый статус из БД одним SELECT, сравнивает с новым.
        Если статус изменился и переход не разрешён — ValidationError.
        Новые заказы (без pk) пропускают проверку — им ещё нечего сравнивать.
        """
        if self.pk:
            # Локальный импорт из-за циклической зависимости:
            # status_transitions импортирует OrderStatus из этого модуля.
            from apps.orders.services.status_transitions import (  # noqa: PLC0415
                is_transition_allowed,
            )

            old = type(self).objects.only("status").get(pk=self.pk)
            if old.status != self.status:
                product_type = self._get_product_type_for_transitions()
                if not is_transition_allowed(old.status, self.status, product_type):
                    raise ValidationError(
                        error_code="invalid_transition",
                        message=f"Недопустимый переход статуса: {old.status} → {self.status}.",
                    )
        super().save(*args, **kwargs)

    def _get_product_type_for_transitions(self) -> str:
        """
        Определить какой граф переходов использовать.
        Если хоть один товар made_to_order — используем расширенный граф.
        Иначе — короткий stock-граф.
        """
        has_made_to_order = self.items.filter(product__product_type="made_to_order").exists()
        return "made_to_order" if has_made_to_order else "stock"


class OrderItem(models.Model):
    """
    Позиция заказа: один товар с зафиксированной ценой и названием.

    Snapshot цены (price) и названия (product_name_snapshot) защищают
    заказ от изменений товара после оформления. Даже если продавец
    поднимет цену — старый заказ хранит стоимость на момент покупки.

    product_uuid_1c нужен для передачи товара в 1С (там товары ищутся
    по UUID, а не по нашему id).
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заказ",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="Товар",
    )
    product_name_snapshot = models.CharField(
        max_length=500,
        verbose_name="Название товара (snapshot)",
    )
    product_uuid_1c = models.UUIDField(
        verbose_name="UUID товара в 1С",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="Количество",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Цена за единицу",
    )
    sum = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма позиции",
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self) -> str:
        return f"{self.product_name_snapshot} x {self.quantity}"


class OrderStatusHistory(models.Model):
    """
    История смены статусов заказа.

    Каждая запись — один переход status_from → status_to с указанием
    кто и когда его сделал. Помогает отвечать на вопросы клиента,
    поддержки и разбирать спорные ситуации.

    Записи создаются автоматически при смене Order.status —
    реализуется через сервис или сигнал в отдельном шаге.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Заказ",
    )
    status_from = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Предыдущий статус",
    )
    status_to = models.CharField(
        max_length=30,
        verbose_name="Новый статус",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_changes",
        verbose_name="Кем изменён",
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Когда изменён",
    )
    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий",
    )
    is_automatic = models.BooleanField(
        default=False,
        verbose_name="Изменён автоматически",
    )

    class Meta:
        verbose_name = "История статуса"
        verbose_name_plural = "История статусов"
        ordering: ClassVar[list[str]] = ["-changed_at"]

    def __str__(self) -> str:
        return f"{self.order.number}: {self.status_from} → {self.status_to}"
