"""
URL-маршруты API заказов.

POST /api/v1/orders/                — оформить заказ (checkout)
GET  /api/v1/orders/                — список моих заказов
GET  /api/v1/orders/{uuid}/         — детали одного заказа
POST /api/v1/orders/{uuid}/cancel/     — отменить свой заказ
POST /api/v1/orders/{uuid}/mark-paid/  — отметить оплаченным (staff)
"""

from django.urls import URLPattern, URLResolver, path

from apps.orders.api.v1 import views

app_name = "orders_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views.OrdersView.as_view(), name="orders"),
    path("<uuid:uuid>/", views.OrderDetailView.as_view(), name="detail"),
    path("<uuid:uuid>/cancel/", views.OrderCancelView.as_view(), name="cancel"),
    path(
        "<uuid:uuid>/mark-paid/",
        views.OrderMarkPaidView.as_view(),
        name="mark-paid",
    ),
]
