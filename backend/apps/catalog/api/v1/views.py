"""
API views для каталога: категории, склады, товары.
"""

from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.catalog.api.v1.serializers import CategorySerializer
from apps.catalog.models import Category


class CategoryListView(generics.ListAPIView):
    """
    Список всех активных категорий каталога.

    Публичный endpoint — доступен без авторизации.
    Категории сортируются по полю order (вручную выставляется в админке),
    затем по имени.

    GET /api/v1/catalog/categories/
    """

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None  # категорий немного, пагинация не нужна

    def get_queryset(self):
        """
        Возвращает только активные категории.
        Сортировка: сначала по полю order, потом по имени.
        """
        return Category.objects.filter(
            is_active=True,
        ).order_by('order', 'name')