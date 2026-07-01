"""
URL-маршруты API корзины.

Три endpoint-а:
  GET,    /api/v1/cart/                       — получить корзину / очистить
  DELETE, /api/v1/cart/
  GET,    /api/v1/cart/count/                 — счётчик
  PUT,    /api/v1/cart/items/<product_id>/    — добавить/обновить позицию
  DELETE, /api/v1/cart/items/<product_id>/    — удалить позицию

Порядок: /count/ идёт перед /items/, чтобы не было теоретической
двусмысленности при добавлении новых маршрутов в будущем.
"""

from django.urls import URLPattern, URLResolver, path

from apps.cart.api.v1 import views_cart

app_name = "cart_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views_cart.CartView.as_view(), name="cart"),
    path("count/", views_cart.CartCountView.as_view(), name="cart-count"),
    path(
        "items/<int:product_id>/",
        views_cart.CartItemView.as_view(),
        name="cart-item",
    ),
]
