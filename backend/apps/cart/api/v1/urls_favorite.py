"""
URL-маршруты API избранного.

Порядок важен: /count/ идёт перед /<product_id>/, иначе Django
попытается сматчить строку "count" как int и вернёт ошибку.
"""

from django.urls import URLPattern, URLResolver, path

from apps.cart.api.v1 import views_favorite

app_name = "favorite_v1"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", views_favorite.FavoriteListView.as_view(), name="favorite-list"),
    path("count/", views_favorite.FavoriteCountView.as_view(), name="favorite-count"),
    path(
        "<int:product_id>/",
        views_favorite.FavoriteDetailView.as_view(),
        name="favorite-detail",
    ),
]
