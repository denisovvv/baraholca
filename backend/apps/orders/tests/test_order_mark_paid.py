"""
HTTP-интеграционные тесты POST /api/v1/orders/{uuid}/mark-paid/.

Заглушка эквайринга: только is_staff отмечает оплату. Логика
смены payment_status и записи истории — в test_payment_status_service.
Здесь фокус на HTTP-контракте: права (is_staff), коды ошибок.
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
    PaymentMethod,
    PaymentStatus,
)
from apps.sellers.models import Seller

User = get_user_model()


class OrderMarkPaidEndpointTestCase(APITestCase):
    """Тесты POST /api/v1/orders/{uuid}/mark-paid/."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.buyer = User.objects.create(
            phone="+79991110001",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        cls.staff = User.objects.create(
            phone="+79992220002",
            first_name="Админ",
            last_name="Админов",
            phone_verified=True,
            is_staff=True,
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

    def _create_order(self, payment_status: str = PaymentStatus.PENDING) -> Order:
        return Order.objects.create(
            number=f"BX-TST-2026-{uuid4().hex[:6]}",
            user=self.buyer,
            seller=self.seller,
            warehouse=self.warehouse,
            status=OrderStatus.CREATED,
            payment_status=payment_status,
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

    def _url(self, order_uuid) -> str:
        return f"/api/v1/orders/{order_uuid}/mark-paid/"

    def test_requires_authentication(self) -> None:
        """Без токена — 401."""
        order = self._create_order()
        response = self.client.post(self._url(order.uuid), {}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_buyer_forbidden(self) -> None:
        """Обычный покупатель (не staff) — 403."""
        order = self._create_order()
        self._auth(self.buyer)

        response = self.client.post(self._url(order.uuid), {}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_staff_marks_paid_success(self) -> None:
        """Staff отмечает оплату — 200, payment_status=paid, paid_at."""
        order = self._create_order()
        self._auth(self.staff)

        response = self.client.post(self._url(order.uuid), {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["payment_status"], PaymentStatus.PAID)
        self.assertIsNotNone(response.data["paid_at"])

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    def test_nonexistent_returns_404(self) -> None:
        """Несуществующий uuid — 404."""
        self._auth(self.staff)
        response = self.client.post(self._url(uuid4()), {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_double_mark_paid_returns_422(self) -> None:
        """Повторная отметка уже оплаченного — 422 invalid_payment_transition."""
        order = self._create_order(payment_status=PaymentStatus.PAID)
        self._auth(self.staff)

        response = self.client.post(self._url(order.uuid), {}, format="json")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"]["code"], "invalid_payment_transition")
