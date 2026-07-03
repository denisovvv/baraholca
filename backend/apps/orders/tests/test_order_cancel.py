"""
HTTP-интеграционные тесты POST /api/v1/orders/{uuid}/cancel/.

Проверяют полный путь: auth → view → сервис → БД → ответ.
Логика освобождения резерва и записи истории — покрыта в
test_order_status_service. Здесь фокус на HTTP-контракте:
права, коды ошибок, изоляция.
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
    OrderStatus,
    OrderStatusHistory,
    PaymentMethod,
    PaymentStatus,
)
from apps.sellers.models import Seller

User = get_user_model()


class OrderCancelEndpointTestCase(APITestCase):
    """Тесты POST /api/v1/orders/{uuid}/cancel/."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create(
            phone="+79991110001",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        cls.other_user = User.objects.create(
            phone="+79992220002",
            first_name="Сергей",
            last_name="Иванов",
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
            address="г.Тестовый, ул.Ленина 1",
            location=Point(40.5, 52.9, srid=4326),
            delivery_area=polygon,
            pickup_available=True,
            is_active=True,
            uuid_1c=uuid4(),
        )

        cls.category = Category.objects.create(name="Тесты", slug="tests")
        cls.product = Product.objects.create(
            name_short="Кружка",
            name_full="Кружка полная",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def _auth(self, user: User) -> None:
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def _create_order(self, user: User, status: str = OrderStatus.PENDING_PAYMENT) -> Order:
        return Order.objects.create(
            number=f"BX-TST-2026-{uuid4().hex[:6]}",
            user=user,
            seller=self.seller,
            warehouse=self.warehouse,
            status=status,
            payment_status=PaymentStatus.PENDING,
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

    def _cancel_url(self, order_uuid) -> str:
        return f"/api/v1/orders/{order_uuid}/cancel/"

    def test_requires_authentication(self) -> None:
        """Без токена — 401 not_authenticated."""
        order = self._create_order(self.user)
        response = self.client.post(self._cancel_url(order.uuid), {}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_cancel_own_order_success(self) -> None:
        """Отмена своего pending_payment заказа — 200, статус cancelled, cancelled_at."""
        order = self._create_order(self.user)
        self._auth(self.user)

        response = self.client.post(self._cancel_url(order.uuid), {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], OrderStatus.CANCELLED)
        self.assertIsNotNone(response.data["cancelled_at"])

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_cancel_other_users_order_returns_404(self) -> None:
        """Чужой заказ — 404 (не раскрываем существование)."""
        order = self._create_order(self.other_user)
        self._auth(self.user)

        response = self.client.post(self._cancel_url(order.uuid), {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_cancel_nonexistent_returns_404(self) -> None:
        """Несуществующий uuid — 404."""
        self._auth(self.user)
        response = self.client.post(self._cancel_url(uuid4()), {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_cancel_shipped_order_returns_422(self) -> None:
        """Заказ уже отгружен — 422 cannot_cancel."""
        order = self._create_order(self.user, status=OrderStatus.SHIPPED)
        self._auth(self.user)

        response = self.client.post(self._cancel_url(order.uuid), {}, format="json")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"]["code"], "cannot_cancel")
        self.assertEqual(response.data["error"]["details"]["current_status"], OrderStatus.SHIPPED)

    def test_cancel_saves_comment_to_history(self) -> None:
        """Комментарий передаётся в OrderStatusHistory."""
        order = self._create_order(self.user)
        self._auth(self.user)

        response = self.client.post(
            self._cancel_url(order.uuid),
            {"comment": "передумал"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        history = OrderStatusHistory.objects.filter(order=order).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.comment, "передумал")
        self.assertEqual(history.status_to, OrderStatus.CANCELLED)
