"""
Integration-тесты PaymentStatusService.

Проверяют путь смены статуса ОПЛАТЫ: валидация → обновление
payment_status → paid_at при оплате → запись PaymentStatusHistory.

Ключевая проверка независимости осей: смена payment_status не
затрагивает физический status.
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase

from apps.catalog.models import Category, Product, Warehouse
from apps.common.exceptions import ValidationError
from apps.orders.models import (
    DeliveryMethod,
    Order,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentStatusHistory,
)
from apps.orders.services.payment_status import PaymentStatusService
from apps.sellers.models import Seller

User = get_user_model()


class PaymentStatusServiceTestCase(TestCase):
    """Тесты PaymentStatusService.change_payment_status."""

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

    def _create_order(self, payment_status: str = PaymentStatus.PENDING) -> Order:
        return Order.objects.create(
            number=f"BX-TST-2026-{uuid4().hex[:6]}",
            user=self.user,
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

    def test_pending_to_paid_sets_paid_at(self) -> None:
        """pending → paid обновляет payment_status и paid_at."""
        order = self._create_order()
        self.assertIsNone(order.paid_at)

        PaymentStatusService.change_payment_status(order, PaymentStatus.PAID, changed_by=self.admin)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertIsNotNone(order.paid_at)

    def test_pending_to_failed_no_paid_at(self) -> None:
        """pending → failed — оплата не прошла, paid_at не ставится."""
        order = self._create_order()

        PaymentStatusService.change_payment_status(order, PaymentStatus.FAILED)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.FAILED)
        self.assertIsNone(order.paid_at)

    def test_failed_to_paid_retry(self) -> None:
        """failed → paid — повторная попытка успешна."""
        order = self._create_order(payment_status=PaymentStatus.FAILED)

        PaymentStatusService.change_payment_status(order, PaymentStatus.PAID)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertIsNotNone(order.paid_at)

    def test_paid_to_refunded(self) -> None:
        """paid → refunded — возврат."""
        order = self._create_order(payment_status=PaymentStatus.PAID)

        PaymentStatusService.change_payment_status(order, PaymentStatus.REFUNDED)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.REFUNDED)

    def test_invalid_transition_raises(self) -> None:
        """pending → refunded запрещён — ValidationError."""
        order = self._create_order()

        with self.assertRaises(ValidationError) as ctx:
            PaymentStatusService.change_payment_status(order, PaymentStatus.REFUNDED)

        self.assertEqual(ctx.exception.error_code, "invalid_payment_transition")

    def test_history_record_created(self) -> None:
        """Смена создаёт запись PaymentStatusHistory с from/to."""
        order = self._create_order()

        PaymentStatusService.change_payment_status(
            order, PaymentStatus.PAID, changed_by=self.admin, comment="Webhook банка"
        )

        history = PaymentStatusHistory.objects.filter(order=order).order_by("-changed_at").first()
        self.assertIsNotNone(history)
        self.assertEqual(history.status_from, PaymentStatus.PENDING)
        self.assertEqual(history.status_to, PaymentStatus.PAID)
        self.assertEqual(history.comment, "Webhook банка")

    def test_payment_change_does_not_affect_order_status(self) -> None:
        """Смена payment_status не трогает физический status (две оси)."""
        order = self._create_order()
        self.assertEqual(order.status, OrderStatus.CREATED)

        PaymentStatusService.change_payment_status(order, PaymentStatus.PAID)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CREATED)
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
