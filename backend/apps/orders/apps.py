"""
Django AppConfig для приложения orders.

Приложение содержит модели заказа, позиций заказа и истории статусов.
Логика оформления заказа (checkout) — в apps/orders/services/,
чтобы не смешивать бизнес-правила с views.
"""

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Конфиг приложения orders."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orders"
    verbose_name = "Заказы"
