"""
URL маршруты для API каталога (v1).
"""

from django.urls import path

from apps.catalog.api.v1 import views


app_name = 'catalog_api_v1'

urlpatterns = [
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('warehouses/', views.WarehouseListView.as_view(), name='warehouse-list'),
]