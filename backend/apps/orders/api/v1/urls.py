"""
URL-маршруты API заказов.

POST /api/v1/orders/ — оформление заказа (checkout).
Другие endpoint-ы (GET списка, детали, отмена) — в Фазах B и C.
"""

from django.urls import URLPattern, URLResolver, path

from apps.orders.api.v1 import views

app_name = "orders_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views.CheckoutView.as_view(), name="checkout"),
]
