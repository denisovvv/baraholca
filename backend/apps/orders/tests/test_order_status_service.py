"""
Integration-тесты OrderStatusService.

Проверяют полный путь смены статуса: валидация → обновление даты →
освобождение резерва при отмене → запись истории.
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase

from apps.catalog.models import Category, Product, ProductStock, Warehouse
from apps.common.exceptions import ValidationError
from apps.orders.models import (
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentMethod,
    PaymentStatus,
)
from apps.orders.services.order_status import OrderStatusService
from apps.sellers.models import Seller

User = get_user_model()


class OrderStatusServiceTestCase(TestCase):
    """Тесты OrderStatusService.change_status."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create(
            phone="+79991110001",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        cls.admin = User.objects.create(
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
            address="г.Тестовый, ул.Ленина 1",
            location=Point(40.5, 52.9, srid=4326),
            delivery_area=polygon,
            pickup_available=True,
            is_active=True,
            uuid_1c=uuid4(),
        )

        cls.category = Category.objects.create(name="Тесты", slug="tests")
        cls.product_stock = Product.objects.create(
            name_short="Кружка stock",
            name_full="Кружка stock полная",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        cls.product_made = Product.objects.create(
            name_short="Фигурка 3D",
            name_full="Фигурка 3D полная",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("1500.00"),
            product_type="made_to_order",
            is_active=True,
            is_available_for_sale=True,
        )

    def _create_order(
        self, status: str = OrderStatus.PENDING_PAYMENT, product: Product | None = None
    ) -> Order:
        product = product or self.product_stock
        order = Order.objects.create(
            number=f"BX-TST-2026-{uuid4().hex[:6]}",
            user=self.user,
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
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name_snapshot=product.name_short,
            product_uuid_1c=uuid4(),
            quantity=2,
            price=Decimal("500.00"),
            sum=Decimal("1000.00"),
        )
        return order

    def _create_stock(self, product: Product, quantity: int, reserved: int) -> ProductStock:
        return ProductStock.objects.create(
            product=product,
            warehouse=self.warehouse,
            quantity=quantity,
            reserved_quantity=reserved,
        )

    def test_valid_transition_updates_paid_at(self) -> None:
        """pending_payment → paid обновляет статус и paid_at."""
        order = self._create_order()
        self.assertIsNone(order.paid_at)

        OrderStatusService.change_status(order, OrderStatus.PAID, changed_by=self.admin)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertIsNotNone(order.paid_at)

    def test_cancel_updates_cancelled_at(self) -> None:
        """pending_payment → cancelled обновляет cancelled_at."""
        order = self._create_order()

        OrderStatusService.change_status(order, OrderStatus.CANCELLED, changed_by=self.user)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertIsNotNone(order.cancelled_at)

    def test_invalid_transition_raises(self) -> None:
        """pending_payment → shipped запрещён — ValidationError invalid_transition."""
        order = self._create_order()

        with self.assertRaises(ValidationError) as ctx:
            OrderStatusService.change_status(order, OrderStatus.SHIPPED)

        self.assertEqual(ctx.exception.error_code, "invalid_transition")

    def test_cancel_releases_reserved_stock(self) -> None:
        """Отмена уменьшает reserved_quantity на количество товара в заказе."""
        order = self._create_order()
        stock = self._create_stock(self.product_stock, quantity=10, reserved=2)

        OrderStatusService.change_status(order, OrderStatus.CANCELLED)

        stock.refresh_from_db()
        self.assertEqual(stock.reserved_quantity, 0)

    def test_history_record_created(self) -> None:
        """При смене статуса создаётся запись OrderStatusHistory с правильными from/to."""
        order = self._create_order()

        OrderStatusService.change_status(
            order, OrderStatus.PAID, changed_by=self.admin, comment="Оплачен клиентом"
        )

        history = OrderStatusHistory.objects.filter(order=order).order_by("-changed_at").first()
        self.assertIsNotNone(history)
        self.assertEqual(history.status_from, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(history.status_to, OrderStatus.PAID)
        self.assertEqual(history.comment, "Оплачен клиентом")

    def test_no_changed_by_marks_automatic(self) -> None:
        """changed_by=None → is_automatic=True (системный переход)."""
        order = self._create_order()

        OrderStatusService.change_status(order, OrderStatus.PAID)

        history = OrderStatusHistory.objects.filter(order=order).order_by("-changed_at").first()
        self.assertTrue(history.is_automatic)
        self.assertIsNone(history.changed_by)

    def test_changed_by_marks_manual(self) -> None:
        """changed_by=user → is_automatic=False, changed_by записан."""
        order = self._create_order()

        OrderStatusService.change_status(order, OrderStatus.PAID, changed_by=self.admin)

        history = OrderStatusHistory.objects.filter(order=order).order_by("-changed_at").first()
        self.assertFalse(history.is_automatic)
        self.assertEqual(history.changed_by, self.admin)

    def test_made_to_order_paid_to_in_production(self) -> None:
        """made_to_order: paid → in_production разрешён (не в графе stock)."""
        order = self._create_order(status=OrderStatus.PAID, product=self.product_made)

        OrderStatusService.change_status(order, OrderStatus.IN_PRODUCTION)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.IN_PRODUCTION)
