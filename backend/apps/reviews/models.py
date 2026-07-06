"""
Модели приложения reviews.

Review — отзыв покупателя на товар: оценка (1-5) и опциональный текст.
Один пользователь может оставить максимум один отзыв на товар
(UniqueConstraint). Проверка "товар реально куплен" — не здесь, а в
сериализаторе (модель не знает про Order, это разделение слоёв).
"""

from typing import ClassVar

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """
    Отзыв покупателя на товар.

    rating обязателен (1-5), text опционален. Один отзыв на товар
    от пользователя — контролируется UniqueConstraint. Проверка что
    товар был куплен и доставлен делается на уровне API (сериализатор),
    чтобы модель не зависела от приложения orders.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Пользователь",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Товар",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Оценка",
    )
    text = models.TextField(
        blank=True,
        verbose_name="Текст отзыва",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создан",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлён",
    )

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering: ClassVar[list[str]] = ["-created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_product_review",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.product}: {self.rating}"
