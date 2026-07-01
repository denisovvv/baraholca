"""
Модели корзины и избранного пользователя.

Пока содержит только Favorite. Модели Cart и CartItem
добавятся отдельными шагами в рамках Этапа 2.
"""

from typing import ClassVar

from django.conf import settings
from django.db import models


class Favorite(models.Model):
    """
    Товар, отмеченный пользователем как избранный.

    Один товар у одного пользователя может быть в избранном
    максимум один раз - контролируется UniqueConstraint.

    Не влияет на остатки и заказы. При деактивации товара
    (product.is_active=False) запись остаётся в БД, но не
    показывается покупателю в списке избранного.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Пользователь",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        verbose_name="Товар",
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Добавлено",
    )

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        ordering: ClassVar[list[str]] = ["-added_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_product_favorite",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.product}"
