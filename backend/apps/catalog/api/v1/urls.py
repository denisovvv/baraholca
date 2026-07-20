"""
URL маршруты для API каталога (v1).
"""

from django.urls import path

from apps.catalog.api.v1 import views, views_search

app_name = "catalog_api_v1"

urlpatterns = [
    path("categories/tree/", views.CategoryTreeView.as_view(), name="category-tree"),
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path("warehouses/nearby/", views.WarehouseNearbyView.as_view(), name="warehouse-nearby"),
    path("warehouses/", views.WarehouseListView.as_view(), name="warehouse-list"),
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/suggest/", views.ProductSuggestView.as_view(), name="product-suggest"),
    path("products/<int:id>/", views.ProductDetailView.as_view(), name="product-detail"),
    path(
        "products/<int:product_id>/seller-products/",
        views.SellerProductsView.as_view(),
        name="product-seller-products",
    ),
    path(
        "products/<int:product_id>/similar/",
        views.SimilarProductsView.as_view(),
        name="product-similar",
    ),
    path(
        "search-history/",
        views_search.SearchHistoryView.as_view(),
        name="search-history",
    ),
    path(
        "search-history/<int:query_id>/",
        views_search.SearchHistoryItemView.as_view(),
        name="search-history-item",
    ),
]
