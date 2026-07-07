"""
HTTP-интеграционные тесты чтения заказов.

Покрывают GET /api/v1/orders/ (список с фильтрами и пагинацией)
и GET /api/v1/orders/{uuid}/ (детали).

Изоляция: пользователь видит только свои заказы, для чужих — 404.
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


class OrdersReadTestCase(APITestCase):
    """Тесты GET /api/v1/orders/ и GET /api/v1/orders/{uuid}/."""

    list_url = "/api/v1/orders/"

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
            name_full="Кружка тестовая",
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

    def _create_order(
        self,
        user: User,
        number: str = "BX-TST-2026-000001",
        status: str = OrderStatus.CREATED,
        payment_status: str = PaymentStatus.PENDING,
    ) -> Order:
        return Order.objects.create(
            number=number,
            user=user,
            seller=self.seller,
            warehouse=self.warehouse,
            status=status,
            payment_status=payment_status,
            delivery_method=DeliveryMethod.COURIER,
            delivery_address="г.Тестовый, ул.Ленина 1",
            delivery_latitude=Decimal("52.9"),
            delivery_longitude=Decimal("40.5"),
            recipient_name="Иванов И.И.",
            recipient_phone="+79990000000",
            payment_method=PaymentMethod.CARD_ONLINE,
            subtotal=Decimal("1000.00"),
            delivery_cost=Decimal("0.00"),
            total=Decimal("1000.00"),
        )

    # -------------------------------------------------------------------
    # GET /api/v1/orders/ — список
    # -------------------------------------------------------------------

    def test_list_requires_authentication(self) -> None:
        """Без токена — 401 not_authenticated."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")

    def test_list_returns_empty_for_new_user(self) -> None:
        """Новый пользователь без заказов — count=0, results=[]."""
        self._auth(self.user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_list_returns_own_orders_only(self) -> None:
        """Возвращает только заказы текущего пользователя, чужие невидимы."""
        self._create_order(self.user, number="BX-TST-2026-000001")
        self._create_order(self.other_user, number="BX-TST-2026-000002")

        self._auth(self.user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["number"], "BX-TST-2026-000001")

    def test_list_returns_both_status_axes(self) -> None:
        """Список отдаёт физический статус И статус оплаты (две оси)."""
        self._create_order(
            self.user,
            number="BX-TST-2026-000042",
            status=OrderStatus.ASSEMBLING,
            payment_status=PaymentStatus.PENDING,
        )
        self._auth(self.user)

        response = self.client.get(self.list_url)
        order_data = response.data["results"][0]

        # Физическая ось
        self.assertEqual(order_data["status"], OrderStatus.ASSEMBLING)
        self.assertEqual(order_data["status_display"], "Собирается")
        # Ось оплаты
        self.assertEqual(order_data["payment_status"], PaymentStatus.PENDING)
        self.assertEqual(order_data["payment_status_display"], "Ожидает оплаты")

    def test_list_shows_paid_status(self) -> None:
        """Оплаченный заказ: payment_status_display = 'Оплачен'."""
        self._create_order(
            self.user,
            number="BX-TST-2026-000037",
            status=OrderStatus.DELIVERED,
            payment_status=PaymentStatus.PAID,
        )
        self._auth(self.user)

        response = self.client.get(self.list_url)
        order_data = response.data["results"][0]

        self.assertEqual(order_data["payment_status"], PaymentStatus.PAID)
        self.assertEqual(order_data["payment_status_display"], "Оплачен")

    def test_list_filter_by_status(self) -> None:
        """?status=assembling возвращает только заказы в сборке."""
        self._create_order(self.user, number="BX-TST-2026-000001", status=OrderStatus.CREATED)
        self._create_order(self.user, number="BX-TST-2026-000002", status=OrderStatus.ASSEMBLING)
        self._create_order(self.user, number="BX-TST-2026-000003", status=OrderStatus.ASSEMBLING)

        self._auth(self.user)
        response = self.client.get(f"{self.list_url}?status=assembling")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_list_filter_by_created_after(self) -> None:
        """?created_after=2026-01-01 фильтрует по дате."""
        self._create_order(self.user, number="BX-TST-2026-000001")

        self._auth(self.user)
        # Фильтр в будущем — должно быть 0 заказов
        response = self.client.get(f"{self.list_url}?created_after=2099-01-01T00:00:00Z")
        self.assertEqual(response.data["count"], 0)

        # Фильтр в прошлом — все заказы попадают
        response = self.client.get(f"{self.list_url}?created_after=2020-01-01T00:00:00Z")
        self.assertEqual(response.data["count"], 1)

    def test_list_pagination(self) -> None:
        """При 25 заказах и PAGE_SIZE=20 — две страницы."""
        for i in range(25):
            self._create_order(self.user, number=f"BX-TST-2026-{i + 1:06d}")

        self._auth(self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

        response_page_2 = self.client.get(f"{self.list_url}?page=2")
        self.assertEqual(len(response_page_2.data["results"]), 5)

    # -------------------------------------------------------------------
    # GET /api/v1/orders/{uuid}/ — детали
    # -------------------------------------------------------------------

    def test_detail_requires_authentication(self) -> None:
        """Без токена — 401."""
        order = self._create_order(self.user)
        response = self.client.get(f"{self.list_url}{order.uuid}/")
        self.assertEqual(response.status_code, 401)

    def test_detail_returns_own_order(self) -> None:
        """Возвращает свой заказ с полными данными по uuid."""
        order = self._create_order(self.user, number="BX-TST-2026-000001")

        self._auth(self.user)
        response = self.client.get(f"{self.list_url}{order.uuid}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["number"], "BX-TST-2026-000001")
        self.assertIn("items", response.data)
        self.assertIn("warehouse", response.data)

    def test_detail_returns_404_for_other_user_order(self) -> None:
        """Чужой заказ не показывается — 404 (не раскрываем существование)."""
        order = self._create_order(self.other_user)

        self._auth(self.user)
        response = self.client.get(f"{self.list_url}{order.uuid}/")
        self.assertEqual(response.status_code, 404)

    def test_detail_returns_404_for_nonexistent_uuid(self) -> None:
        """Несуществующий uuid — 404."""
        self._auth(self.user)
        random_uuid = uuid4()
        response = self.client.get(f"{self.list_url}{random_uuid}/")
        self.assertEqual(response.status_code, 404)
