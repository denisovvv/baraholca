"""
HTTP-интеграционные тесты API отзывов.

Покрывают публичный список, создание с проверкой покупки
(только на доставленный товар), уникальность, изоляцию
редактирования/удаления.
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Category, Product, Warehouse
from apps.orders.models import (
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from apps.reviews.models import Review
from apps.sellers.models import Seller

User = get_user_model()


class ReviewEndpointsTestCase(APITestCase):
    """Тесты API отзывов."""

    reviews_url = "/api/v1/reviews/"

    @classmethod
    def setUpTestData(cls) -> None:
        cls.buyer = User.objects.create(
            phone="+79991110001",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        cls.other_user = User.objects.create(
            phone="+79992220002",
            first_name="Сергей",
            last_name="Сидоров",
            phone_verified=True,
        )

        cls.seller = Seller.objects.create(
            name="Тестовый ИП",
            short_name="Тестовый",
            inn="111111111111",
            ogrnip="222222222222222",
            contact_phone="+79990000001",
            order_prefix="TST",
        )

        radius = 0.1
        polygon = Polygon(
            (
                (40.5 - radius, 52.9 - radius),
                (40.5 + radius, 52.9 - radius),
                (40.5 + radius, 52.9 + radius),
                (40.5 - radius, 52.9 + radius),
                (40.5 - radius, 52.9 - radius),
            ),
            srid=4326,
        )
        cls.warehouse = Warehouse.objects.create(
            seller=cls.seller,
            name="Тестовый склад",
            address="г.Тестовый",
            location=Point(40.5, 52.9, srid=4326),
            delivery_area=polygon,
            pickup_available=True,
            is_active=True,
            uuid_1c=uuid4(),
        )

        cls.category = Category.objects.create(name="Тесты", slug="tests")
        cls.product_bought = Product.objects.create(
            name_short="Купленный",
            name_full="Купленный товар",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        cls.product_not_bought = Product.objects.create(
            name_short="Некупленный",
            name_full="Некупленный товар",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("300.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def _auth(self, user: User) -> None:
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def _create_delivered_order(self, user: User, product: Product) -> Order:
        """Создать доставленный заказ с товаром — база для отзыва."""
        order = Order.objects.create(
            number=f"BX-TST-2026-{uuid4().hex[:6]}",
            user=user,
            seller=self.seller,
            warehouse=self.warehouse,
            status=OrderStatus.DELIVERED,
            payment_status=PaymentStatus.PAID,
            delivery_method=DeliveryMethod.COURIER,
            delivery_address="г.Тестовый",
            delivery_latitude=Decimal("52.9"),
            delivery_longitude=Decimal("40.5"),
            recipient_name="Иванов",
            recipient_phone="+79990000000",
            payment_method=PaymentMethod.CARD_ONLINE,
            subtotal=Decimal("500.00"),
            delivery_cost=Decimal("0.00"),
            total=Decimal("500.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name_snapshot=product.name_short,
            product_uuid_1c=uuid4(),
            quantity=1,
            price=Decimal("500.00"),
            sum=Decimal("500.00"),
        )
        return order

    def _create_review(
        self,
        user: User,
        product: Product,
        rating: int = 5,
        is_published: bool = True,
    ) -> Review:
        return Review.objects.create(
            user=user, product=product, rating=rating, is_published=is_published
        )

    def test_list_public_no_auth(self) -> None:
        """Список отзывов доступен без токена."""
        self._create_review(self.buyer, self.product_bought)
        response = self.client.get(self.reviews_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_list_filter_by_product(self) -> None:
        """?product={id} возвращает только отзывы этого товара."""
        self._create_review(self.buyer, self.product_bought)
        self._create_review(self.other_user, self.product_not_bought)

        response = self.client.get(f"{self.reviews_url}?product={self.product_bought.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_list_author_name_anonymized(self) -> None:
        """Автор показывается как 'Иван П.'."""
        self._create_review(self.buyer, self.product_bought)
        response = self.client.get(self.reviews_url)
        self.assertEqual(response.data["results"][0]["author_name"], "Иван П.")

    def test_create_requires_auth(self) -> None:
        """Создание без токена — 401."""
        response = self.client.post(
            self.reviews_url,
            {"product": self.product_bought.id, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_create_on_delivered_product_success(self) -> None:
        """Отзыв на купленный доставленный товар — 201."""
        self._create_delivered_order(self.buyer, self.product_bought)
        self._auth(self.buyer)

        response = self.client.post(
            self.reviews_url,
            {"product": self.product_bought.id, "rating": 5, "text": "Отлично"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["rating"], 5)
        self.assertEqual(response.data["author_name"], "Иван П.")

    def test_create_on_not_bought_product_forbidden(self) -> None:
        """Отзыв на не купленный товар — 422."""
        self._auth(self.buyer)

        response = self.client.post(
            self.reviews_url,
            {"product": self.product_not_bought.id, "rating": 4},
            format="json",
        )
        self.assertEqual(response.status_code, 422)

    def test_create_duplicate_forbidden(self) -> None:
        """Повторный отзыв на тот же товар — 422."""
        self._create_delivered_order(self.buyer, self.product_bought)
        self._create_review(self.buyer, self.product_bought)
        self._auth(self.buyer)

        response = self.client.post(
            self.reviews_url,
            {"product": self.product_bought.id, "rating": 3},
            format="json",
        )
        self.assertEqual(response.status_code, 422)

    def test_update_own_review(self) -> None:
        """Редактировать свой отзыв — 200, rating изменён."""
        review = self._create_review(self.buyer, self.product_bought, rating=3)
        self._auth(self.buyer)

        response = self.client.patch(
            f"{self.reviews_url}{review.id}/",
            {"rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)

    def test_update_others_review_returns_404(self) -> None:
        """Редактировать чужой отзыв — 404 (изоляция)."""
        review = self._create_review(self.other_user, self.product_bought)
        self._auth(self.buyer)

        response = self.client.patch(
            f"{self.reviews_url}{review.id}/",
            {"rating": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_unpublished_review_hidden_from_list(self) -> None:
        """Скрытый отзыв (is_published=False) не виден в публичном списке."""
        self._create_review(self.buyer, self.product_bought, is_published=True)
        self._create_review(self.other_user, self.product_bought, is_published=False)

        response = self.client.get(self.reviews_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_delete_own_review(self) -> None:
        """Удалить свой отзыв — 204."""
        review = self._create_review(self.buyer, self.product_bought)
        self._auth(self.buyer)

        response = self.client.delete(f"{self.reviews_url}{review.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Review.objects.filter(id=review.id).exists())
