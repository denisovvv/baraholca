"""
URL-маршруты API избранного.

Порядок важен: /count/ идёт перед /<product_id>/, иначе Django
попытается сматчить строку "count" как int и вернёт ошибку.
"""

from django.urls import URLPattern, URLResolver, path

from apps.cart.api.v1 import views

app_name = "cart_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views.FavoriteListView.as_view(), name="favorite-list"),
    path("count/", views.FavoriteCountView.as_view(), name="favorite-count"),
    path(
        "<int:product_id>/",
        views.FavoriteDetailView.as_view(),
        name="favorite-detail",
    ),
]
