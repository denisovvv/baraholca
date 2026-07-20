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
    ProductGroup,
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


class ProductVariantsTests(APITestCase):
    """Тесты вариантов товара на карточке (группа вариантов)."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Иванов",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            order_prefix="PVA",
        )
        # Группа вариантов "Чехол iPhone 11 Pro Max"
        self.group = ProductGroup.objects.create(name="Чехол iPhone 11 Pro Max")

        # Вариант жёлтый (своя цена)
        self.yellow = Product.objects.create(
            name_short="Чехол жёлтый",
            name_full="Чехол iPhone 11 Pro Max жёлтый",
            seller=self.seller,
            group=self.group,
            variant_color="Жёлтый",
            base_price=Decimal("1500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Вариант голубой (другая цена)
        self.blue = Product.objects.create(
            name_short="Чехол голубой",
            name_full="Чехол iPhone 11 Pro Max голубой",
            seller=self.seller,
            group=self.group,
            variant_color="Голубой",
            base_price=Decimal("1600.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Товар без группы (без вариантов)
        self.standalone = Product.objects.create(
            name_short="Кружка",
            name_full="Кружка обычная",
            seller=self.seller,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def _detail(self, product_id):
        return self.client.get(f"/api/v1/catalog/products/{product_id}/")

    def test_variants_include_all_group_products(self):
        """Карточка варианта отдаёт все варианты группы, включая себя."""
        response = self._detail(self.yellow.id)
        self.assertEqual(response.status_code, 200)
        variants = response.data["variants"]
        ids = {v["id"] for v in variants}
        self.assertIn(self.yellow.id, ids)
        self.assertIn(self.blue.id, ids)
        self.assertEqual(len(variants), 2)

    def test_variant_has_color_and_price(self):
        """Вариант содержит цвет и свою цену."""
        response = self._detail(self.yellow.id)
        variants = {v["variant_color"]: v for v in response.data["variants"]}
        self.assertEqual(variants["Жёлтый"]["effective_price"], "1500.00")
        self.assertEqual(variants["Голубой"]["effective_price"], "1600.00")

    def test_variant_has_availability(self):
        """Вариант содержит флаг доступности."""
        response = self._detail(self.yellow.id)
        for v in response.data["variants"]:
            self.assertIn("is_available", v)
            self.assertTrue(v["is_available"])

    def test_variants_sorted_by_id(self):
        """Варианты отсортированы по id."""
        response = self._detail(self.yellow.id)
        ids = [v["id"] for v in response.data["variants"]]
        self.assertEqual(ids, sorted(ids))

    def test_product_without_group_empty_variants(self):
        """Товар без группы — пустой список вариантов."""
        response = self._detail(self.standalone.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["variants"], [])


class ProductSuggestTests(APITestCase):
    """Тесты автодополнения поиска (подсказки)."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Иванов",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            order_prefix="SUG",
        )
        # Товары с "чехол" в названии
        self.case1 = Product.objects.create(
            name_short="Чехол iPhone 15",
            name_full="Чехол для iPhone 15 силиконовый",
            seller=self.seller,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        self.case2 = Product.objects.create(
            name_short="Чехол ноутбука",
            name_full="Чехол для ноутбука 15 дюймов",
            seller=self.seller,
            base_price=Decimal("800.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Совпадение только в полном названии
        self.full_only = Product.objects.create(
            name_short="Аксессуар А1",
            name_full="Универсальный чехол-книжка",
            seller=self.seller,
            base_price=Decimal("300.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Не совпадает
        self.other = Product.objects.create(
            name_short="Кружка",
            name_full="Кружка керамическая",
            seller=self.seller,
            base_price=Decimal("400.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Неактивный с "чехол"
        self.hidden = Product.objects.create(
            name_short="Чехол скрытый",
            name_full="Чехол неактивный",
            seller=self.seller,
            base_price=Decimal("100.00"),
            product_type="stock",
            is_active=False,
            is_available_for_sale=True,
        )
        self.url = "/api/v1/catalog/products/suggest/"

    def test_suggest_by_name_short(self):
        """Находит товары по краткому названию."""
        response = self.client.get(self.url, {"q": "чехол"})
        self.assertEqual(response.status_code, 200)
        names = {item["name_short"] for item in response.data}
        self.assertIn("Чехол iPhone 15", names)
        self.assertIn("Чехол ноутбука", names)

    def test_suggest_by_name_full(self):
        """Находит по полному названию (совпадение только там)."""
        response = self.client.get(self.url, {"q": "книжка"})
        names = {item["name_short"] for item in response.data}
        self.assertIn("Аксессуар А1", names)

    def test_suggest_case_insensitive(self):
        """Регистронезависимый поиск."""
        response = self.client.get(self.url, {"q": "ЧЕХОЛ"})
        self.assertGreaterEqual(len(response.data), 2)

    def test_suggest_excludes_inactive(self):
        """Неактивные товары не в подсказках."""
        response = self.client.get(self.url, {"q": "чехол"})
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Чехол скрытый", names)

    def test_suggest_empty_query_empty_result(self):
        """Пустой запрос — пустой список."""
        response = self.client.get(self.url, {"q": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_suggest_no_query_param_empty(self):
        """Без параметра q — пустой список."""
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 0)

    def test_suggest_returns_only_id_and_name(self):
        """Подсказка содержит только id и name_short."""
        response = self.client.get(self.url, {"q": "чехол"})
        item = response.data[0]
        self.assertEqual(set(item.keys()), {"id", "name_short"})


class ProductFilterExtendedTests(APITestCase):
    """Тесты расширенных фильтров: тип, рейтинг, скидка, сортировки."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Иванов",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            order_prefix="FLT",
        )
        self.category = Category.objects.create(name="Разное")
        self.user = get_user_model().objects.create(
            phone="+79991112200",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )

        # Товар со скидкой, тип stock
        self.discounted = Product.objects.create(
            name_short="Со скидкой",
            name_full="Товар со скидкой",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("1000.00"),
            discount_price=Decimal("700.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Товар без скидки, тип made_to_order (под заказ)
        self.made = Product.objects.create(
            name_short="Под заказ",
            name_full="Товар под заказ",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("2000.00"),
            product_type="made_to_order",
            is_active=True,
            is_available_for_sale=True,
        )
        # Товар с высоким рейтингом
        self.rated_high = Product.objects.create(
            name_short="Рейтинг высокий",
            name_full="Товар с высоким рейтингом",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        Review.objects.create(user=self.user, product=self.rated_high, rating=5, is_published=True)
        self.url = "/api/v1/catalog/products/"

    def test_filter_by_product_type(self):
        """Фильтр по типу товара (под заказ)."""
        response = self.client.get(self.url, {"product_type": "made_to_order"})
        names = {item["name_short"] for item in response.data["results"]}
        self.assertIn("Под заказ", names)
        self.assertNotIn("Со скидкой", names)

    def test_filter_has_discount(self):
        """Фильтр только со скидкой."""
        response = self.client.get(self.url, {"has_discount": "true"})
        names = {item["name_short"] for item in response.data["results"]}
        self.assertIn("Со скидкой", names)
        self.assertNotIn("Под заказ", names)

    def test_filter_rating_min(self):
        """Фильтр по минимальному рейтингу."""
        response = self.client.get(self.url, {"rating_min": "4"})
        names = {item["name_short"] for item in response.data["results"]}
        self.assertIn("Рейтинг высокий", names)
        # Товары без отзывов не проходят фильтр рейтинга
        self.assertNotIn("Со скидкой", names)

    def test_ordering_by_rating(self):
        """Сортировка по рейтингу (сначала высокий, без рейтинга — вниз)."""
        response = self.client.get(self.url, {"ordering": "-rating_sort"})
        results = response.data["results"]
        # Товар с рейтингом 5 первый; товары без отзывов (rating_sort=0) внизу
        self.assertEqual(results[0]["name_short"], "Рейтинг высокий")

    def test_ordering_by_newest(self):
        """Сортировка по новизне (сначала новые)."""
        response = self.client.get(self.url, {"ordering": "-created_at"})
        results = response.data["results"]
        # Последний созданный (rated_high) — первый
        self.assertEqual(results[0]["name_short"], "Рейтинг высокий")


class CatalogVariantCollapseTests(APITestCase):
    """Схлопывание вариантов в каталоге: группа = одна карточка."""

    def setUp(self):
        self.seller = Seller.objects.create(
            name="ИП Иванов",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            order_prefix="CVC",
        )
        self.group = ProductGroup.objects.create(name="Чехол iPhone 11")

        # Три варианта одной группы (первый по id — представитель)
        self.variant1 = Product.objects.create(
            name_short="Чехол жёлтый",
            name_full="Чехол жёлтый",
            seller=self.seller,
            group=self.group,
            variant_color="Жёлтый",
            base_price=Decimal("1500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        self.variant2 = Product.objects.create(
            name_short="Чехол голубой",
            name_full="Чехол голубой",
            seller=self.seller,
            group=self.group,
            variant_color="Голубой",
            base_price=Decimal("1600.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        self.variant3 = Product.objects.create(
            name_short="Чехол красный",
            name_full="Чехол красный",
            seller=self.seller,
            group=self.group,
            variant_color="Красный",
            base_price=Decimal("1700.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        # Обычный товар без группы
        self.standalone = Product.objects.create(
            name_short="Кружка",
            name_full="Кружка",
            seller=self.seller,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        self.url = "/api/v1/catalog/products/"

    def test_group_collapsed_to_one_card(self):
        """Группа вариантов показывается одной карточкой в каталоге."""
        response = self.client.get(self.url)
        ids = {item["id"] for item in response.data["results"]}
        # Представитель (первый по id) есть
        self.assertIn(self.variant1.id, ids)
        # Остальные варианты схлопнуты (не в каталоге)
        self.assertNotIn(self.variant2.id, ids)
        self.assertNotIn(self.variant3.id, ids)

    def test_standalone_product_shown(self):
        """Товар без группы показывается как обычно."""
        response = self.client.get(self.url)
        ids = {item["id"] for item in response.data["results"]}
        self.assertIn(self.standalone.id, ids)

    def test_representative_has_variants_count(self):
        """Представитель показывает число вариантов группы."""
        response = self.client.get(self.url)
        rep = next(item for item in response.data["results"] if item["id"] == self.variant1.id)
        self.assertEqual(rep["variants_count"], 3)

    def test_standalone_variants_count_zero(self):
        """Товар без группы: variants_count = 0."""
        response = self.client.get(self.url)
        item = next(item for item in response.data["results"] if item["id"] == self.standalone.id)
        self.assertEqual(item["variants_count"], 0)

    def test_catalog_total_count(self):
        """В каталоге: 1 представитель группы + 1 обычный = 2 карточки."""
        response = self.client.get(self.url)
        self.assertEqual(response.data["count"], 2)
