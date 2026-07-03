"""
URL-маршруты API заказов.

POST /api/v1/orders/          — оформить заказ (checkout)
GET  /api/v1/orders/          — список моих заказов
GET  /api/v1/orders/{uuid}/   — детали одного заказа
"""

from django.urls import URLPattern, URLResolver, path

from apps.orders.api.v1 import views

app_name = "orders_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views.OrdersView.as_view(), name="orders"),
    path("<uuid:uuid>/", views.OrderDetailView.as_view(), name="detail"),
]
