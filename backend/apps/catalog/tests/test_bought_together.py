"""
Тесты endpoint "Покупают вместе" (аналитика по доставленным заказам).
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product, Warehouse
from apps.orders.models import (
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from apps.sellers.models import Seller

User = get_user_model()


class BoughtTogetherTests(APITestCase):
    """Товары, покупаемые вместе с текущим."""

    def setUp(self):
        self.user = User.objects.create(
            phone="+79991112233",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        self.seller = Seller.objects.create(
            name="ИП Иванов",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            order_prefix="BGT",
        )
        self.category = Category.objects.create(name="Инструменты")
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
        self.warehouse = Warehouse.objects.create(
            seller=self.seller,
            name="Тестовый склад",
            address="г.Тест, ул.Ленина 1",
            location=Point(40.5, 52.9, srid=4326),
            delivery_area=polygon,
            pickup_available=True,
            is_active=True,
            uuid_1c=uuid4(),
        )

        # A — текущий товар, B и C — сопутствующие
        self.a = self._product("Перчатки")
        self.b = self._product("Мешки")
        self.c = self._product("Скотч")

        self._order_counter = 0

    def _product(self, name):
        return Product.objects.create(
            name_short=name,
            name_full=f"{name} полное",
            seller=self.seller,
            category=self.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )

    def _delivered_order_with(self, products):
        """Создать доставленный заказ с указанными товарами."""
        self._order_counter += 1
        order = Order.objects.create(
            number=f"BX-BGT-2026-{self._order_counter:06d}",
            user=self.user,
            seller=self.seller,
            warehouse=self.warehouse,
            status=OrderStatus.DELIVERED,
            payment_status=PaymentStatus.PAID,
            delivery_method=DeliveryMethod.COURIER,
            delivery_address="г.Тест, ул.Ленина 1",
            delivery_latitude=Decimal("52.9"),
            delivery_longitude=Decimal("40.5"),
            recipient_name="Иванов И.И.",
            recipient_phone="+79990000000",
            payment_method=PaymentMethod.CARD_ONLINE,
            subtotal=Decimal("1000.00"),
            delivery_cost=Decimal("0.00"),
            total=Decimal("1000.00"),
        )
        for prod in products:
            OrderItem.objects.create(
                order=order,
                product=prod,
                product_name_snapshot=prod.name_short,
                product_uuid_1c=uuid4(),
                quantity=1,
                price=prod.base_price,
                sum=prod.base_price,
            )
        return order

    def _create_order_with_status(self, products, status):
        """Заказ с произвольным статусом (для проверки фильтра delivered)."""
        self._order_counter += 1
        order = Order.objects.create(
            number=f"BX-BGT-2026-{self._order_counter:06d}",
            user=self.user,
            seller=self.seller,
            warehouse=self.warehouse,
            status=status,
            payment_status=PaymentStatus.PENDING,
            delivery_method=DeliveryMethod.COURIER,
            delivery_address="г.Тест, ул.Ленина 1",
            delivery_latitude=Decimal("52.9"),
            delivery_longitude=Decimal("40.5"),
            recipient_name="Иванов И.И.",
            recipient_phone="+79990000000",
            payment_method=PaymentMethod.CARD_ONLINE,
            subtotal=Decimal("1000.00"),
            delivery_cost=Decimal("0.00"),
            total=Decimal("1000.00"),
        )
        for prod in products:
            OrderItem.objects.create(
                order=order,
                product=prod,
                product_name_snapshot=prod.name_short,
                product_uuid_1c=uuid4(),
                quantity=1,
                price=prod.base_price,
                sum=prod.base_price,
            )
        return order

    def _url(self, product_id):
        return f"/api/v1/catalog/products/{product_id}/bought-together/"

    def test_recommends_co_purchased(self):
        """Товары из доставленных заказов с текущим — рекомендуются."""
        self._delivered_order_with([self.a, self.b])
        response = self.client.get(self._url(self.a.id))
        self.assertEqual(response.status_code, 200)
        names = {item["name_short"] for item in response.data}
        self.assertIn("Мешки", names)

    def test_sorted_by_frequency(self):
        """Более частый спутник — выше."""
        # B с A дважды, C с A однажды
        self._delivered_order_with([self.a, self.b])
        self._delivered_order_with([self.a, self.b])
        self._delivered_order_with([self.a, self.c])
        response = self.client.get(self._url(self.a.id))
        names = [item["name_short"] for item in response.data]
        # Мешки (2 раза) выше Скотча (1 раз)
        self.assertEqual(names[0], "Мешки")

    def test_excludes_current_product(self):
        """Текущий товар не рекомендуется сам себе."""
        self._delivered_order_with([self.a, self.b])
        response = self.client.get(self._url(self.a.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Перчатки", names)

    def test_only_delivered_orders(self):
        """Недоставленные заказы не учитываются."""
        # Заказ [A, C] в статусе created — не должен влиять
        self._create_order_with_status([self.a, self.c], OrderStatus.CREATED)
        response = self.client.get(self._url(self.a.id))
        names = {item["name_short"] for item in response.data}
        self.assertNotIn("Скотч", names)

    def test_no_orders_empty(self):
        """Нет доставленных заказов — пустой список."""
        response = self.client.get(self._url(self.a.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_404_for_missing(self):
        """Несуществующий товар — 404."""
        response = self.client.get(self._url(999999))
        self.assertEqual(response.status_code, 404)
