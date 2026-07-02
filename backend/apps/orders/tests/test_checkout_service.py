"""
Интеграционные тесты CheckoutService — реальная БД, реальные транзакции.

Покрывают координацию checkout, не алгоритм распределения
(алгоритм покрыт в test_warehouse_allocator.py).
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, ProductStock, Warehouse
from apps.common.exceptions import ValidationError
from apps.orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from apps.orders.services.checkout import CheckoutService
from apps.sellers.models import Seller

User = get_user_model()


class CheckoutServiceTestCase(TestCase):
    """Тесты CheckoutService.perform_checkout."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create(
            phone="+79991110001",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )

        cls.seller_a = Seller.objects.create(
            name="ИП Первый",
            short_name="Первый",
            inn="100000000001",
            ogrnip="200000000000001",
            contact_phone="+79990001",
            order_prefix="FST",
        )
        cls.seller_b = Seller.objects.create(
            name="ИП Второй",
            short_name="Второй",
            inn="100000000002",
            ogrnip="200000000000002",
            contact_phone="+79990002",
            order_prefix="SND",
        )

        cls.warehouse_a1 = cls._create_warehouse("A-1", cls.seller_a, 52.9, 40.5)
        cls.warehouse_a2 = cls._create_warehouse("A-2", cls.seller_a, 52.95, 40.5)
        cls.warehouse_b1 = cls._create_warehouse("B-1", cls.seller_b, 52.9, 40.5)

        cls.category = Category.objects.create(name="Тесты", slug="tests")

        cls.product_a1 = cls._create_product("Кружка A", cls.seller_a, "500.00")
        cls.product_a2 = cls._create_product("Футболка A", cls.seller_a, "1000.00")
        cls.product_b1 = cls._create_product("Носки B", cls.seller_b, "200.00")

        cls.courier_payload = {
            "delivery_method": "courier",
            "delivery_address": "г.Тестовый, ул.Ленина 1",
            "delivery_latitude": Decimal("52.9"),
            "delivery_longitude": Decimal("40.5"),
            "delivery_comment": "звонить за 10 мин",
            "recipient_name": "Иванов И.И.",
            "recipient_phone": "+79990000000",
            "payment_method": "card_online",
            "comment": "",
        }
        cls.pickup_payload = {
            "delivery_method": "pickup",
            "warehouse_uuid": cls.warehouse_a1.uuid_1c,
            "recipient_name": "Иванов И.И.",
            "recipient_phone": "+79990000000",
            "payment_method": "cash_on_delivery",
            "comment": "",
        }

    @classmethod
    def _create_warehouse(cls, name: str, seller: Seller, lat: float, lng: float) -> Warehouse:
        radius = 0.1
        polygon = Polygon(
            (
                (lng - radius, lat - radius),
                (lng + radius, lat - radius),
                (lng + radius, lat + radius),
                (lng - radius, lat + radius),
                (lng - radius, lat - radius),
            ),
            srid=4326,
        )
        return Warehouse.objects.create(
            seller=seller,
            name=name,
            address=f"адрес {name}",
            location=Point(lng, lat, srid=4326),
            delivery_area=polygon,
            pickup_available=True,
            is_active=True,
            uuid_1c=uuid4(),
        )

    @classmethod
    def _create_product(cls, name: str, seller: Seller, price: str) -> Product:
        return Product.objects.create(
            name_short=name,
            name_full=f"{name} полное",
            seller=seller,
            category=cls.category,
            base_price=Decimal(price),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def _setup_cart(self, items: list[tuple[Product, int]]) -> Cart:
        cart, _ = Cart.objects.get_or_create(user=self.user)
        for product, qty in items:
            CartItem.objects.create(cart=cart, product=product, quantity=qty)
        return cart

    def _setup_stock(
        self, product: Product, warehouse: Warehouse, quantity: int, reserved: int = 0
    ) -> ProductStock:
        return ProductStock.objects.create(
            product=product,
            warehouse=warehouse,
            quantity=quantity,
            reserved_quantity=reserved,
        )

    def test_happy_path_courier(self) -> None:
        """Courier: корзина одного продавца превращается в 1 Order."""
        self._setup_cart([(self.product_a1, 2)])
        self._setup_stock(self.product_a1, self.warehouse_a1, quantity=10)

        orders = CheckoutService.perform_checkout(self.user, self.courier_payload)

        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order.status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(order.seller, self.seller_a)
        self.assertEqual(order.subtotal, Decimal("1000.00"))
        self.assertEqual(order.total, Decimal("1000.00"))
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 1)
        history = OrderStatusHistory.objects.filter(order=order).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.status_to, OrderStatus.PENDING_PAYMENT)
        self.assertTrue(history.is_automatic)
        stock = ProductStock.objects.get(product=self.product_a1, warehouse=self.warehouse_a1)
        self.assertEqual(stock.reserved_quantity, 2)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)

    def test_happy_path_pickup(self) -> None:
        """Pickup: заказ создаётся на переданный склад."""
        self._setup_cart([(self.product_a1, 3)])
        self._setup_stock(self.product_a1, self.warehouse_a1, quantity=10)

        orders = CheckoutService.perform_checkout(self.user, self.pickup_payload)

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].warehouse, self.warehouse_a1)
        self.assertEqual(orders[0].delivery_method, "pickup")

    def test_empty_cart(self) -> None:
        """Пустая корзина — 422 empty_cart."""
        with self.assertRaises(ValidationError) as ctx:
            CheckoutService.perform_checkout(self.user, self.courier_payload)
        self.assertEqual(ctx.exception.error_code, "empty_cart")

    def test_inactive_product(self) -> None:
        """Неактивный товар — 422 product_unavailable с details."""
        self.product_a1.is_active = False
        self.product_a1.save()
        self._setup_cart([(self.product_a1, 1)])

        with self.assertRaises(ValidationError) as ctx:
            CheckoutService.perform_checkout(self.user, self.courier_payload)
        exc = ctx.exception
        self.assertEqual(exc.error_code, "product_unavailable")
        self.assertIsNotNone(exc.details)
        self.assertEqual(exc.details[0]["product_id"], self.product_a1.pk)

    def test_not_enough_stock_rolls_back(self) -> None:
        """
        Недостаточно остатков — 422, транзакция откатилась:
        Order не создан, корзина цела, reserved не увеличилось.
        """
        self._setup_cart([(self.product_a1, 10)])
        self._setup_stock(self.product_a1, self.warehouse_a1, quantity=3)

        with self.assertRaises(ValidationError) as ctx:
            CheckoutService.perform_checkout(self.user, self.courier_payload)
        self.assertEqual(ctx.exception.error_code, "not_enough_stock")

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)
        stock = ProductStock.objects.get(product=self.product_a1, warehouse=self.warehouse_a1)
        self.assertEqual(stock.reserved_quantity, 0)

    def test_multi_seller_creates_multiple_orders(self) -> None:
        """
        Товары от двух продавцов → два Order с разными seller.
        """
        self._setup_cart([(self.product_a1, 1), (self.product_b1, 2)])
        self._setup_stock(self.product_a1, self.warehouse_a1, quantity=10)
        self._setup_stock(self.product_b1, self.warehouse_b1, quantity=10)

        orders = CheckoutService.perform_checkout(self.user, self.courier_payload)

        self.assertEqual(len(orders), 2)
        sellers = {o.seller for o in orders}
        self.assertEqual(sellers, {self.seller_a, self.seller_b})

    def test_warehouse_split_same_seller(self) -> None:
        """
        Один продавец, товары в разных складах → два Order.
        """
        self._setup_cart([(self.product_a1, 1), (self.product_a2, 1)])
        self._setup_stock(self.product_a1, self.warehouse_a1, quantity=10)
        self._setup_stock(self.product_a2, self.warehouse_a2, quantity=10)

        orders = CheckoutService.perform_checkout(self.user, self.courier_payload)

        self.assertEqual(len(orders), 2)
        warehouses = {o.warehouse for o in orders}
        self.assertEqual(warehouses, {self.warehouse_a1, self.warehouse_a2})
        for o in orders:
            self.assertEqual(o.seller, self.seller_a)

    def test_order_number_generation(self) -> None:
        """
        Номер формируется как BX-{prefix}-{год}-{seq}.
        Первый заказ — 000001, второй — 000002.
        """
        self._setup_cart([(self.product_a1, 1)])
        self._setup_stock(self.product_a1, self.warehouse_a1, quantity=100)

        orders_1 = CheckoutService.perform_checkout(self.user, self.courier_payload)
        self.assertTrue(orders_1[0].number.startswith("BX-FST-"))
        self.assertTrue(orders_1[0].number.endswith("-000001"))

        self._setup_cart([(self.product_a1, 1)])
        orders_2 = CheckoutService.perform_checkout(self.user, self.courier_payload)
        self.assertTrue(orders_2[0].number.endswith("-000002"))

    def test_cart_cleared_on_success(self) -> None:
        """Корзина очищается после успешного checkout, Cart-запись остаётся."""
        cart = self._setup_cart([(self.product_a1, 1)])
        self._setup_stock(self.product_a1, self.warehouse_a1, quantity=10)

        CheckoutService.perform_checkout(self.user, self.courier_payload)

        self.assertEqual(CartItem.objects.filter(cart=cart).count(), 0)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())
