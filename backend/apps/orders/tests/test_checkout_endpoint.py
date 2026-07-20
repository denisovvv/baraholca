"""
HTTP-интеграционные тесты POST /api/v1/orders/.

Проверяют полный путь: JWT auth → APIClient → view → сериализатор →
сервис → БД → ответ клиенту. Логика распределения и транзакции
уже покрыты в test_warehouse_allocator и test_checkout_service —
здесь фокус на HTTP-контракте.
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, ProductStock, Warehouse
from apps.sellers.models import Seller

User = get_user_model()


class CheckoutEndpointTestCase(APITestCase):
    """Тесты HTTP endpoint POST /api/v1/orders/."""

    checkout_url = "/api/v1/orders/"

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create(
            phone="+79991110001",
            first_name="Иван",
            last_name="Петров",
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

    def _auth(self) -> None:
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def _setup_cart(self, quantity: int = 1) -> None:
        cart, _ = Cart.objects.get_or_create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=quantity)

    def _setup_stock(self, quantity: int) -> None:
        ProductStock.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity=quantity,
            reserved_quantity=0,
        )

    def _courier_payload(self) -> dict:
        return {
            "delivery_method": "courier",
            "delivery_address": "г.Тестовый, ул.Ленина 1",
            "delivery_latitude": "52.9",
            "delivery_longitude": "40.5",
            "delivery_comment": "звонить за 10 мин",
            "recipient_name": "Иванов И.И.",
            "recipient_phone": "+79990000000",
            "payment_method": "card_online",
            "comment": "тестовый заказ",
        }

    def _pickup_payload(self) -> dict:
        return {
            "delivery_method": "pickup",
            "warehouse_uuid": str(self.warehouse.uuid_1c),
            "recipient_name": "Иванов И.И.",
            "recipient_phone": "+79990000000",
            "payment_method": "cash_on_delivery",
        }

    def test_requires_authentication(self) -> None:
        """Без токена — 401 not_authenticated."""
        response = self.client.post(self.checkout_url, self._courier_payload(), format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")

    def test_courier_happy_path(self) -> None:
        """Courier: 201 со списком созданных Order."""
        self._setup_cart(quantity=2)
        self._setup_stock(quantity=10)
        self._auth()

        response = self.client.post(self.checkout_url, self._courier_payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        order_data = response.data[0]
        self.assertIn("uuid", order_data)
        self.assertIn("number", order_data)
        self.assertTrue(order_data["number"].startswith("BX-TST-"))
        self.assertEqual(order_data["status"], "created")
        self.assertEqual(len(order_data["items"]), 1)
        self.assertEqual(order_data["items"][0]["quantity"], 2)
        self.assertIn("warehouse", order_data)
        self.assertEqual(order_data["warehouse"]["name"], "Тестовый склад")

    def test_sbp_payment_method(self) -> None:
        """Checkout принимает оплату по СБП, заказ сохраняется с sbp."""
        self._setup_cart(quantity=1)
        self._setup_stock(quantity=10)
        self._auth()
        payload = self._courier_payload()
        payload["payment_method"] = "sbp"

        response = self.client.post(self.checkout_url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        order_data = response.data[0]
        self.assertEqual(order_data["payment_method"], "sbp")
        self.assertEqual(order_data["payment_method_display"], "СБП")

    def test_pickup_happy_path(self) -> None:
        """Pickup: 201 с одним заказом на выбранный склад."""
        self._setup_cart(quantity=1)
        self._setup_stock(quantity=10)
        self._auth()

        response = self.client.post(self.checkout_url, self._pickup_payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data[0]["delivery_method"], "pickup")

    def test_courier_missing_address_returns_422(self) -> None:
        """Courier без delivery_address — 422 с ошибкой валидации по полю."""
        self._setup_cart()
        self._auth()
        payload = self._courier_payload()
        payload.pop("delivery_address")

        response = self.client.post(self.checkout_url, payload, format="json")

        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)

    def test_pickup_missing_warehouse_uuid_returns_422(self) -> None:
        """Pickup без warehouse_uuid — 422."""
        self._setup_cart()
        self._auth()
        payload = self._pickup_payload()
        payload.pop("warehouse_uuid")

        response = self.client.post(self.checkout_url, payload, format="json")

        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)

    def test_invalid_delivery_method_returns_422(self) -> None:
        """Некорректный delivery_method — 422."""
        self._setup_cart()
        self._auth()
        payload = self._courier_payload()
        payload["delivery_method"] = "invalid_method"

        response = self.client.post(self.checkout_url, payload, format="json")

        self.assertEqual(response.status_code, 422)

    def test_empty_cart_returns_422(self) -> None:
        """Пустая корзина — 422 empty_cart."""
        self._auth()

        response = self.client.post(self.checkout_url, self._courier_payload(), format="json")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"]["code"], "empty_cart")

    def test_not_enough_stock_returns_422_with_details(self) -> None:
        """
        Недостаточно остатков — 422 not_enough_stock с details по товарам.
        """
        self._setup_cart(quantity=10)
        self._setup_stock(quantity=3)
        self._auth()

        response = self.client.post(self.checkout_url, self._courier_payload(), format="json")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"]["code"], "not_enough_stock")
        self.assertIn("details", response.data["error"])
        detail = response.data["error"]["details"][0]
        self.assertEqual(detail["product_id"], self.product.pk)
        self.assertEqual(detail["requested"], 10)
        self.assertEqual(detail["available"], 3)
