"""
Тесты endpoints каталога.

Проверяем список товаров с фильтрами, карточку товара,
геопоиск складов и дерево категорий.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from apps.catalog.models import (
    Category,
    Product,
    ProductCharacteristic,
    Warehouse,
)
from apps.reviews.models import Review
from apps.sellers.models import Seller

User = get_user_model()


class ProductListTests(APITestCase):
    """Тесты списка товаров с фильтрацией."""

    def setUp(self):
        # Создаём продавца
        self.seller = Seller.objects.create(
            name="ИП Тестовый",
            short_name="Тестовый",
            inn="123456789012",
            ogrnip="123456789012345",
        )
        # Категория
        self.category = Category.objects.create(name="Кружки")

        # Товар с базовой ценой 500, без скидки
        self.cheap = Product.objects.create(
            name_short="Дешёвая кружка",
            name_full="Дешёвая кружка полное",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Товар с базовой 1000 и скидкой до 700
        self.discounted = Product.objects.create(
            name_short="Дорогая со скидкой",
            name_full="Дорогая со скидкой полное",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("1000.00"),
            discount_price=Decimal("700.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Невидимый товар (не активен) — не должен попадать в список
        self.hidden = Product.objects.create(
            name_short="Скрытый",
            name_full="Скрытый полное",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("300.00"),
            product_type="stock",
            is_active=False,
            is_available_for_sale=True,
        )
        self.url = "/api/v1/catalog/products/"

    def test_list_returns_only_visible(self):
        """В списке только видимые товары (скрытый не показан)."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # 2 видимых из 3 созданных
        self.assertEqual(response.data["count"], 2)

    def test_filter_by_price_uses_effective_price(self):
        """
        Фильтр по цене работает на эффективную цену.
        Товар с базой 1000 и скидкой 700 должен попадать в диапазон 600-800,
        потому что его реальная цена 700, а не 1000.
        """
        response = self.client.get(self.url, {"price_min": 600, "price_max": 800})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["name_short"],
            "Дорогая со скидкой",
        )

    def test_search_by_name(self):
        """Поиск находит товар по названию."""
        response = self.client.get(self.url, {"search": "Дешёвая"})
        self.assertEqual(response.data["count"], 1)


class ProductDetailTests(APITestCase):
    """Тесты карточки товара."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Тестовый",
            short_name="Тестовый",
            inn="123456789012",
            ogrnip="123456789012345",
        )
        self.product = Product.objects.create(
            name_short="Кружка",
            name_full="Кружка полное название",
            seller=self.seller,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def test_detail_returns_product(self):
        """Карточка существующего товара возвращается со статусом 200."""
        response = self.client.get(f"/api/v1/catalog/products/{self.product.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name_short"], "Кружка")

    def test_detail_returns_characteristics_in_order(self):
        """Карточка отдаёт характеристики товара в порядке order."""
        ProductCharacteristic.objects.create(
            product=self.product, name="Вес", value="450 г", order=2
        )
        ProductCharacteristic.objects.create(
            product=self.product, name="Материал", value="Керамика", order=1
        )

        response = self.client.get(f"/api/v1/catalog/products/{self.product.id}/")

        self.assertEqual(response.status_code, 200)
        chars = response.data["characteristics"]
        self.assertEqual(len(chars), 2)
        # Порядок: Материал (order=1) перед Вес (order=2)
        self.assertEqual(chars[0]["name"], "Материал")
        self.assertEqual(chars[0]["value"], "Керамика")
        self.assertEqual(chars[1]["name"], "Вес")

    def test_detail_no_characteristics_empty_list(self):
        """Товар без характеристик — пустой список."""
        response = self.client.get(f"/api/v1/catalog/products/{self.product.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["characteristics"], [])

    def test_nonexistent_returns_not_found_error(self):
        """Несуществующий товар — 404 в едином контракте {error: {code, message}}."""
        response = self.client.get("/api/v1/catalog/products/99999/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "not_found")
        self.assertTrue(response.data["error"]["message"])


class WarehouseNearbyTests(APITestCase):
    """Тесты геопоиска ближайших складов."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Тестовый",
            short_name="Тестовый",
            inn="123456789012",
            ogrnip="123456789012345",
        )
        # Склад в Воронеже
        self.voronezh = Warehouse.objects.create(
            seller=self.seller,
            name="Воронежский",
            address="Воронеж",
            location=Point(39.20, 51.66, srid=4326),
            is_active=True,
        )
        # Склад в Старом Осколе (~100 км от Воронежа)
        self.oskol = Warehouse.objects.create(
            seller=self.seller,
            name="Оскольский",
            address="Старый Оскол",
            location=Point(37.83, 51.30, srid=4326),
            is_active=True,
        )
        self.url = "/api/v1/catalog/warehouses/nearby/"

    def test_nearby_sorts_by_distance(self):
        """
        При запросе из Воронежа воронежский склад идёт первым,
        оскольский — вторым.
        """
        response = self.client.get(self.url, {"lat": 51.66, "lon": 39.20})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["name"], "Воронежский")
        self.assertEqual(response.data[1]["name"], "Оскольский")

    def test_nearby_includes_distance(self):
        """Каждый склад содержит поле distance_km."""
        response = self.client.get(self.url, {"lat": 51.66, "lon": 39.20})
        self.assertIn("distance_km", response.data[0])

    def test_missing_coordinates_returns_validation_error(self):
        """Без координат — 422 с error.code='coordinates_missing'."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "coordinates_missing")
        self.assertTrue(response.data["error"]["message"])

    def test_invalid_coordinates_returns_validation_error(self):
        """Координаты-буквы — 422 с error.code='coordinates_not_numeric'."""
        response = self.client.get(self.url, {"lat": "abc", "lon": "39"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "coordinates_not_numeric")
        self.assertTrue(response.data["error"]["message"])

    def test_out_of_range_coordinates_returns_validation_error(self):
        """Широта вне диапазона -90..90 — 422 с error.code='coordinates_out_of_range'."""
        response = self.client.get(self.url, {"lat": "200", "lon": "39"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "coordinates_out_of_range")
        self.assertTrue(response.data["error"]["message"])


class CategoryTreeTests(APITestCase):
    """Тесты дерева категорий."""

    def setUp(self):
        # Корневая категория
        self.root = Category.objects.create(name="Кружки")
        # Дочерняя
        self.child = Category.objects.create(name="Керамические", parent=self.root)
        self.url = "/api/v1/catalog/categories/tree/"

    def test_tree_returns_roots(self):
        """Дерево возвращает корневые категории."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)  # одна корневая
        self.assertEqual(response.data[0]["name"], "Кружки")

    def test_tree_includes_children(self):
        """Корневая категория содержит дочернюю во вложенном children."""
        response = self.client.get(self.url)
        children = response.data[0]["children"]
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["name"], "Керамические")


class ProductRatingTests(APITestCase):
    """Тесты агрегированного рейтинга товара в каталоге."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Тестовый",
            short_name="Тестовый",
            inn="123456789012",
            ogrnip="123456789012345",
        )
        self.category = Category.objects.create(name="Кружки")
        self.user1 = User.objects.create(
            phone="+79991110001",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        self.user2 = User.objects.create(
            phone="+79992220002",
            first_name="Сергей",
            last_name="Сидоров",
            phone_verified=True,
        )
        self.user3 = User.objects.create(
            phone="+79993330003",
            first_name="Пётр",
            last_name="Кузнецов",
            phone_verified=True,
        )
        self.rated = Product.objects.create(
            name_short="Товар с отзывами",
            name_full="Товар с отзывами полное",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        self.no_reviews = Product.objects.create(
            name_short="Товар без отзывов",
            name_full="Товар без отзывов полное",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("300.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        self.url = "/api/v1/catalog/products/"

    def _get_product_data(self, response, name_short):
        """Найти товар в ответе по name_short."""
        for item in response.data["results"]:
            if item["name_short"] == name_short:
                return item
        return None

    def test_rating_aggregates_published_reviews(self):
        """Средний балл и счётчик считаются по опубликованным отзывам."""
        Review.objects.create(user=self.user1, product=self.rated, rating=5)
        Review.objects.create(user=self.user2, product=self.rated, rating=4)
        Review.objects.create(user=self.user3, product=self.rated, rating=3)

        response = self.client.get(self.url)
        data = self._get_product_data(response, "Товар с отзывами")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["rating_avg"], 4.0)
        self.assertEqual(data["reviews_count"], 3)

    def test_hidden_review_excluded_from_rating(self):
        """Скрытый отзыв (is_published=False) не влияет на балл и счётчик."""
        Review.objects.create(user=self.user1, product=self.rated, rating=5)
        Review.objects.create(user=self.user2, product=self.rated, rating=5)
        Review.objects.create(user=self.user3, product=self.rated, rating=1, is_published=False)

        response = self.client.get(self.url)
        data = self._get_product_data(response, "Товар с отзывами")

        # Скрытая единица не учтена: среднее 5.0, счётчик 2
        self.assertEqual(data["rating_avg"], 5.0)
        self.assertEqual(data["reviews_count"], 2)

    def test_product_without_reviews_null_rating(self):
        """Товар без отзывов: rating_avg=None, reviews_count=0."""
        response = self.client.get(self.url)
        data = self._get_product_data(response, "Товар без отзывов")

        self.assertIsNone(data["rating_avg"])
        self.assertEqual(data["reviews_count"], 0)


class SellerProductsTests(APITestCase):
    """Тесты endpoint "Ещё у этого продавца"."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Иванов",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            order_prefix="SPA",
        )
        self.other_seller = Seller.objects.create(
            name="ИП Петров",
            short_name="Петров",
            inn="210987654321",
            ogrnip="543210987654321",
            order_prefix="SPB",
        )
        self.category = Category.objects.create(name="Инструменты")

        # Текущий товar (для него ищем рекомендации)
        self.current = Product.objects.create(
            name_short="Дрель",
            name_full="Дрель ударная",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("3000.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Другие товары того же продавца
        self.same_1 = Product.objects.create(
            name_short="Шуруповёрт",
            name_full="Шуруповёрт аккумуляторный",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("4000.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        self.same_2 = Product.objects.create(
            name_short="Молоток",
            name_full="Молоток слесарный",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Товар другого продавца — не должен попадать
        self.foreign = Product.objects.create(
            name_short="Пила",
            name_full="Пила чужого продавца",
            seller=self.other_seller,
            category=self.category,
            base_price=Decimal("2000.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Неактивный товар того же продавца — не должен попадать
        self.hidden = Product.objects.create(
            name_short="Ножовка",
            name_full="Ножовка скрытая",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("800.00"),
            product_type="stock",
            is_active=False,
            is_available_for_sale=True,
        )

    def _url(self, product_id):
        return f"/api/v1/catalog/products/{product_id}/seller-products/"

    def test_returns_other_products_of_same_seller(self):
        """Отдаёт другие товары того же продавца."""
        response = self.client.get(self._url(self.current.id))
        self.assertEqual(response.status_code, 200)
        names = {item["name_short"] for item in response.data}
        self.assertIn("Шуруповёрт", names)
        self.assertIn("Молоток", names)

    def test_excludes_current_product(self):
        """Текущий товар не показывается в своих рекомендациях."""
        response = self.client.get(self._url(self.current.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Дрель", names)

    def test_excludes_other_sellers(self):
        """Товары других продавцов не показываются."""
        response = self.client.get(self._url(self.current.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Пила", names)

    def test_excludes_inactive_products(self):
        """Неактивные товары не показываются."""
        response = self.client.get(self._url(self.current.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Ножовка", names)

    def test_404_for_missing_product(self):
        """Несуществующий товар — 404."""
        response = self.client.get(self._url(999999))
        self.assertEqual(response.status_code, 404)


class SimilarProductsTests(APITestCase):
    """Тесты endpoint "Похожие товары" (та же категория)."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Иванов",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            order_prefix="SIA",
        )
        self.tools = Category.objects.create(name="Инструменты")
        self.dishes = Category.objects.create(name="Посуда")

        # Текущий товар в категории "Инструменты"
        self.current = Product.objects.create(
            name_short="Дрель",
            name_full="Дрель ударная",
            seller=self.seller,
            category=self.tools,
            base_price=Decimal("3000.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Другой товар той же категории
        self.same_category = Product.objects.create(
            name_short="Молоток",
            name_full="Молоток слесарный",
            seller=self.seller,
            category=self.tools,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Товар другой категории — не должен попадать
        self.other_category = Product.objects.create(
            name_short="Кружка",
            name_full="Кружка керамическая",
            seller=self.seller,
            category=self.dishes,
            base_price=Decimal("400.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Неактивный товар той же категории — не должен попадать
        self.hidden = Product.objects.create(
            name_short="Ножовка",
            name_full="Ножовка скрытая",
            seller=self.seller,
            category=self.tools,
            base_price=Decimal("800.00"),
            product_type="stock",
            is_active=False,
            is_available_for_sale=True,
        )
        # Товар без категории
        self.no_category = Product.objects.create(
            name_short="Разное",
            name_full="Товар без категории",
            seller=self.seller,
            category=None,
            base_price=Decimal("100.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def _url(self, product_id):
        return f"/api/v1/catalog/products/{product_id}/similar/"

    def test_returns_same_category_products(self):
        """Отдаёт другие товары той же категории."""
        response = self.client.get(self._url(self.current.id))
        self.assertEqual(response.status_code, 200)
        names = {item["name_short"] for item in response.data}
        self.assertIn("Молоток", names)

    def test_excludes_current_product(self):
        """Текущий товар не показывается."""
        response = self.client.get(self._url(self.current.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Дрель", names)

    def test_excludes_other_category(self):
        """Товары другой категории не показываются."""
        response = self.client.get(self._url(self.current.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Кружка", names)

    def test_excludes_inactive(self):
        """Неактивные товары не показываются."""
        response = self.client.get(self._url(self.current.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Ножовка", names)

    def test_product_without_category_returns_empty(self):
        """Товар без категории — пустой список похожих."""
        response = self.client.get(self._url(self.no_category.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_404_for_missing_product(self):
        """Несуществующий товар — 404."""
        response = self.client.get(self._url(999999))
        self.assertEqual(response.status_code, 404)
