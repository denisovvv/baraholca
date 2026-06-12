"""
Тесты бизнес-логики моделей каталога.

Проверяем методы и валидации Product, ProductStock, Category —
напрямую, без HTTP.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.catalog.models import Category, Product, ProductStock, Warehouse
from apps.sellers.models import Seller


class ProductPriceTests(TestCase):
    """Тесты расчёта эффективной цены товара."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name='ИП Тестовый', short_name='Тестовый',
            inn='123456789012', ogrnip='123456789012345',
        )

    def test_effective_price_without_discount(self):
        """Без скидки эффективная цена равна базовой."""
        product = Product.objects.create(
            name_short='Кружка', name_full='Кружка',
            seller=self.seller,
            base_price=Decimal('500.00'),
            product_type='stock',
        )
        self.assertEqual(product.get_effective_price(), Decimal('500.00'))

    def test_effective_price_with_discount(self):
        """Со скидкой эффективная цена равна скидочной."""
        product = Product.objects.create(
            name_short='Кружка', name_full='Кружка',
            seller=self.seller,
            base_price=Decimal('500.00'),
            discount_price=Decimal('400.00'),
            product_type='stock',
        )
        self.assertEqual(product.get_effective_price(), Decimal('400.00'))


class ProductValidationTests(TestCase):
    """Тесты валидации товара."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name='ИП Тестовый', short_name='Тестовый',
            inn='123456789012', ogrnip='123456789012345',
        )

    def test_discount_higher_than_base_is_invalid(self):
        """Скидочная цена не может быть выше базовой."""
        product = Product(
            name_short='Кружка', name_full='Кружка',
            seller=self.seller,
            base_price=Decimal('500.00'),
            discount_price=Decimal('600.00'),  # выше базовой — ошибка
            product_type='stock',
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_made_to_order_requires_production_time(self):
        """Товар под заказ без срока изготовления — невалиден."""
        product = Product(
            name_short='Олень', name_full='Олень',
            seller=self.seller,
            base_price=Decimal('800.00'),
            product_type='made_to_order',
            production_time_days=None,  # не указан — ошибка
        )
        with self.assertRaises(ValidationError):
            product.full_clean()


class ProductStockTests(TestCase):
    """Тесты остатков на складах."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name='ИП Тестовый', short_name='Тестовый',
            inn='123456789012', ogrnip='123456789012345',
        )
        self.product = Product.objects.create(
            name_short='Кружка', name_full='Кружка',
            seller=self.seller,
            base_price=Decimal('500.00'),
            product_type='stock',
        )
        from django.contrib.gis.geos import Point
        self.warehouse = Warehouse.objects.create(
            seller=self.seller, name='Склад', address='Адрес',
            location=Point(39.0, 51.0, srid=4326),
        )

    def test_available_quantity(self):
        """Доступное количество = общее минус зарезервированное."""
        stock = ProductStock.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity=10,
            reserved_quantity=3,
        )
        self.assertEqual(stock.available_quantity, 7)

    def test_reserved_more_than_quantity_invalid(self):
        """Зарезервировано больше, чем есть — невалидно."""
        stock = ProductStock(
            product=self.product,
            warehouse=self.warehouse,
            quantity=5,
            reserved_quantity=10,  # больше чем есть — ошибка
        )
        with self.assertRaises(ValidationError):
            stock.full_clean()


class CategoryValidationTests(TestCase):
    """Тесты валидации иерархии категорий."""

    def test_category_cannot_be_its_own_parent(self):
        """Категория не может быть родителем самой себя."""
        cat = Category.objects.create(name='Кружки')
        cat.parent = cat
        with self.assertRaises(ValidationError):
            cat.full_clean()

    def test_depth_limit(self):
        """Глубина больше 3 уровней — невалидна."""
        level1 = Category.objects.create(name='Уровень 1')
        level2 = Category.objects.create(name='Уровень 2', parent=level1)
        level3 = Category.objects.create(name='Уровень 3', parent=level2)
        # Четвёртый уровень — должен быть отклонён
        level4 = Category(name='Уровень 4', parent=level3)
        with self.assertRaises(ValidationError):
            level4.full_clean()
            