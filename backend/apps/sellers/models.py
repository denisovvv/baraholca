from django.conf import settings
from django.db import models


class Seller(models.Model):
    """
    Продавец на маркетплейсе. На старте — три ИП.
    """

    # Идентификатор из 1С
    uuid_1c = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        verbose_name="UUID в 1С",
        help_text="Уникальный идентификатор продавца в системе 1С",
    )

    # Юридические данные
    name = models.CharField(
        max_length=255, verbose_name="Название", help_text="Например: ИП Иванов И.И."
    )
    short_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Краткое название",
        help_text='Для отображения покупателю, например: "Лавка Иванова"',
    )
    inn = models.CharField(max_length=12, unique=True, verbose_name="ИНН")
    ogrnip = models.CharField(max_length=15, unique=True, verbose_name="ОГРНИП")

    # Контактные данные
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Контактный телефон")
    contact_email = models.EmailField(blank=True, verbose_name="Контактный email")

    # Связь с пользователем-администратором
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_sellers",
        verbose_name="Администратор",
        help_text="Пользователь, который управляет этим продавцом в админке",
    )

    # Статус
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Если выключено — товары продавца не отображаются в каталоге",
    )

    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")

    class Meta:
        verbose_name = "Продавец"
        verbose_name_plural = "Продавцы"
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name


class SellerStaff(models.Model):
    """
    Связь пользователя с продавцом и его ролью в команде продавца.
    Один пользователь может работать у нескольких продавцов с разными ролями.
    """

    ROLE_ADMIN = "admin"
    ROLE_MANAGER = "manager"
    ROLE_STOREKEEPER = "storekeeper"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Администратор"),
        (ROLE_MANAGER, "Менеджер заказов"),
        (ROLE_STOREKEEPER, "Кладовщик"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_roles",
        verbose_name="Пользователь",
    )
    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="staff", verbose_name="Продавец"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="Роль")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Сотрудник продавца"
        verbose_name_plural = "Сотрудники продавцов"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "seller"], name="unique_user_seller_role")
        ]

    def __str__(self):
        return f"{self.user} → {self.seller} ({self.get_role_display()})"
