"""
Тесты endpoints каталога.

Проверяем список товаров с фильтрами, карточку товара,
геопоиск складов и дерево категорий.
"""

from decimal import Decimal

from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product, Warehouse
from apps.sellers.models import Seller


class ProductListTests(APITestCase):
    """Тесты списка товаров с фильтрацией."""

    def setUp(self):
        # Создаём продавца
        self.seller = Seller.objects.create(
            name='ИП Тестовый',
            short_name='Тестовый',
            inn='123456789012',
            ogrnip='123456789012345',
        )
        # Категория
        self.category = Category.objects.create(name='Кружки')

        # Товар с базовой ценой 500, без скидки
        self.cheap = Product.objects.create(
            name_short='Дешёвая кружка',
            name_full='Дешёвая кружка полное',
            seller=self.seller,
            category=self.category,
            base_price=Decimal('500.00'),
            product_type='stock',
            is_active=True,
            is_available_for_sale=True,
        )
        # Товар с базовой 1000 и скидкой до 700
        self.discounted = Product.objects.create(
            name_short='Дорогая со скидкой',
            name_full='Дорогая со скидкой полное',
            seller=self.seller,
            category=self.category,
            base_price=Decimal('1000.00'),
            discount_price=Decimal('700.00'),
            product_type='stock',
            is_active=True,
            is_available_for_sale=True,
        )
        # Невидимый товар (не активен) — не должен попадать в список
        self.hidden = Product.objects.create(
            name_short='Скрытый',
            name_full='Скрытый полное',
            seller=self.seller,
            category=self.category,
            base_price=Decimal('300.00'),
            product_type='stock',
            is_active=False,
            is_available_for_sale=True,
        )
        self.url = '/api/v1/catalog/products/'

    def test_list_returns_only_visible(self):
        """В списке только видимые товары (скрытый не показан)."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # 2 видимых из 3 созданных
        self.assertEqual(response.data['count'], 2)

    def test_filter_by_price_uses_effective_price(self):
        """
        Фильтр по цене работает на эффективную цену.
        Товар с базой 1000 и скидкой 700 должен попадать в диапазон 600-800,
        потому что его реальная цена 700, а не 1000.
        """
        response = self.client.get(self.url, {'price_min': 600, 'price_max': 800})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['name_short'],
            'Дорогая со скидкой',
        )

    def test_search_by_name(self):
        """Поиск находит товар по названию."""
        response = self.client.get(self.url, {'search': 'Дешёвая'})
        self.assertEqual(response.data['count'], 1)


class ProductDetailTests(APITestCase):
    """Тесты карточки товара."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name='ИП Тестовый', short_name='Тестовый',
            inn='123456789012', ogrnip='123456789012345',
        )
        self.product = Product.objects.create(
            name_short='Кружка',
            name_full='Кружка полное название',
            seller=self.seller,
            base_price=Decimal('500.00'),
            product_type='stock',
            is_active=True,
            is_available_for_sale=True,
        )

    def test_detail_returns_product(self):
        """Карточка существующего товара возвращается со статусом 200."""
        response = self.client.get(f'/api/v1/catalog/products/{self.product.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name_short'], 'Кружка')

    def test_nonexistent_returns_404(self):
        """Несуществующий товар — 404."""
        response = self.client.get('/api/v1/catalog/products/99999/')
        self.assertEqual(response.status_code, 404)


class WarehouseNearbyTests(APITestCase):
    """Тесты геопоиска ближайших складов."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name='ИП Тестовый', short_name='Тестовый',
            inn='123456789012', ogrnip='123456789012345',
        )
        # Склад в Воронеже
        self.voronezh = Warehouse.objects.create(
            seller=self.seller,
            name='Воронежский',
            address='Воронеж',
            location=Point(39.20, 51.66, srid=4326),
            is_active=True,
        )
        # Склад в Старом Осколе (~100 км от Воронежа)
        self.oskol = Warehouse.objects.create(
            seller=self.seller,
            name='Оскольский',
            address='Старый Оскол',
            location=Point(37.83, 51.30, srid=4326),
            is_active=True,
        )
        self.url = '/api/v1/catalog/warehouses/nearby/'

    def test_nearby_sorts_by_distance(self):
        """
        При запросе из Воронежа воронежский склад идёт первым,
        оскольский — вторым.
        """
        response = self.client.get(self.url, {'lat': 51.66, 'lon': 39.20})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['name'], 'Воронежский')
        self.assertEqual(response.data[1]['name'], 'Оскольский')

    def test_nearby_includes_distance(self):
        """Каждый склад содержит поле distance_km."""
        response = self.client.get(self.url, {'lat': 51.66, 'lon': 39.20})
        self.assertIn('distance_km', response.data[0])

    def test_missing_coordinates_returns_400(self):
        """Без координат — ошибка валидации 400."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)

    def test_invalid_coordinates_returns_400(self):
        """Координаты-буквы — ошибка 400."""
        response = self.client.get(self.url, {'lat': 'abc', 'lon': '39'})
        self.assertEqual(response.status_code, 400)


class CategoryTreeTests(APITestCase):
    """Тесты дерева категорий."""

    def setUp(self):
        # Корневая категория
        self.root = Category.objects.create(name='Кружки')
        # Дочерняя
        self.child = Category.objects.create(name='Керамические', parent=self.root)
        self.url = '/api/v1/catalog/categories/tree/'

    def test_tree_returns_roots(self):
        """Дерево возвращает корневые категории."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)  # одна корневая
        self.assertEqual(response.data[0]['name'], 'Кружки')

    def test_tree_includes_children(self):
        """Корневая категория содержит дочернюю во вложенном children."""
        response = self.client.get(self.url)
        children = response.data[0]['children']
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]['name'], 'Керамические')
