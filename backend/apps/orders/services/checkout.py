"""
Оркестратор оформления заказа: превращает корзину в один или несколько Order.

Всё в одной транзакции — при любой ошибке никаких частичных заказов,
резервов или изменений корзины.
"""

import uuid as uuid_pkg
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone

from apps.cart.models import CartItem
from apps.catalog.models import ProductStock
from apps.common.exceptions import ValidationError
from apps.orders.models import (
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
)
from apps.orders.services.allocation import (
    AllocatedItem,
    AllocationResult,
    WarehouseAllocation,
)
from apps.orders.services.warehouse_allocator import WarehouseAllocator
from apps.sellers.models import Seller

if TYPE_CHECKING:
    from apps.catalog.models import Product, Warehouse
    from apps.users.models import User


class CheckoutService:
    """Оркестратор оформления заказа."""

    @staticmethod
    @transaction.atomic
    def perform_checkout(user: "User", payload: dict[str, Any]) -> list[Order]:
        """
        Оформить корзину как один или несколько заказов.

        Raises:
            ValidationError("empty_cart"): корзина пуста.
            ValidationError("product_unavailable"): товар неактивен.
            NoDeliveryAvailableError: courier — нет склада доставки.
            PickupNotAvailableError: pickup — склад не принимает самовывоз.
            NotFoundError("warehouse_not_found"): pickup — склад не найден.
            ValidationError("not_enough_stock"): недостаточно остатков.
        """
        cart_items = CheckoutService._get_cart_items(user)
        if not cart_items:
            raise ValidationError(
                error_code="empty_cart",
                message="Корзина пуста.",
            )

        CheckoutService._check_products_active(cart_items)
        items_by_seller = CheckoutService._group_by_seller(cart_items)
        allocations_by_seller = CheckoutService._run_allocations(items_by_seller, payload)

        created_orders: list[Order] = []
        for seller, allocation_result in allocations_by_seller.items():
            for allocation in allocation_result.allocations:
                order = CheckoutService._create_order(
                    user=user,
                    seller=seller,
                    allocation=allocation,
                    payload=payload,
                )
                created_orders.append(order)

        CheckoutService._clear_cart(user)
        return created_orders

    @staticmethod
    def _get_cart_items(user: "User") -> list[CartItem]:
        return list(
            CartItem.objects.filter(cart__user=user).select_related("product", "product__seller")
        )

    @staticmethod
    def _check_products_active(cart_items: list[CartItem]) -> None:
        unavailable = [
            item.product
            for item in cart_items
            if not item.product.is_active or not item.product.is_available_for_sale
        ]
        if not unavailable:
            return

        details = [{"product_id": p.pk, "product_name": p.name_short} for p in unavailable]
        raise ValidationError(
            error_code="product_unavailable",
            message="Некоторые товары недоступны для покупки.",
            details=details,
        )

    @staticmethod
    def _group_by_seller(
        cart_items: list[CartItem],
    ) -> dict["Seller", list[tuple["Product", int]]]:
        grouped: dict[Seller, list[tuple[Product, int]]] = {}
        for item in cart_items:
            seller = item.product.seller
            grouped.setdefault(seller, []).append((item.product, item.quantity))
        return grouped

    @staticmethod
    def _run_allocations(
        items_by_seller: dict["Seller", list[tuple["Product", int]]],
        payload: dict[str, Any],
    ) -> dict["Seller", AllocationResult]:
        delivery_method = payload["delivery_method"]
        allocations: dict[Seller, AllocationResult] = {}
        for seller, items in items_by_seller.items():
            if delivery_method == DeliveryMethod.COURIER:
                delivery_point = Point(
                    float(payload["delivery_longitude"]),
                    float(payload["delivery_latitude"]),
                    srid=4326,
                )
                allocations[seller] = WarehouseAllocator.allocate_for_courier(
                    seller=seller, items=items, delivery_point=delivery_point
                )
            else:
                allocations[seller] = WarehouseAllocator.allocate_for_pickup(
                    seller=seller,
                    items=items,
                    warehouse_uuid=payload["warehouse_uuid"],
                )
        return allocations

    @staticmethod
    def _create_order(
        user: "User",
        seller: "Seller",
        allocation: WarehouseAllocation,
        payload: dict[str, Any],
    ) -> Order:
        item_sums: list[tuple[AllocatedItem, Decimal, Decimal]] = []
        subtotal = Decimal("0.00")
        for allocated in allocation.items:
            price = allocated.product.get_effective_price()
            item_sum = price * allocated.quantity
            item_sums.append((allocated, price, item_sum))
            subtotal += item_sum

        delivery_cost = Decimal("0.00")
        total = subtotal + delivery_cost
        number = CheckoutService._generate_order_number(seller)

        order = Order.objects.create(
            number=number,
            user=user,
            seller=seller,
            warehouse=allocation.warehouse,
            status=OrderStatus.PENDING_PAYMENT,
            delivery_method=payload["delivery_method"],
            delivery_address=payload.get("delivery_address", ""),
            delivery_latitude=payload.get("delivery_latitude"),
            delivery_longitude=payload.get("delivery_longitude"),
            delivery_comment=payload.get("delivery_comment", ""),
            recipient_name=payload["recipient_name"],
            recipient_phone=payload["recipient_phone"],
            payment_method=payload["payment_method"],
            subtotal=subtotal,
            delivery_cost=delivery_cost,
            total=total,
            comment=payload.get("comment", ""),
        )

        for allocated, price, item_sum in item_sums:
            OrderItem.objects.create(
                order=order,
                product=allocated.product,
                product_name_snapshot=allocated.product.name_short,
                product_uuid_1c=allocated.product.uuid_1c or uuid_pkg.uuid4(),
                quantity=allocated.quantity,
                price=price,
                sum=item_sum,
            )
            CheckoutService._reserve_stock(
                product=allocated.product,
                warehouse=allocation.warehouse,
                quantity=allocated.quantity,
            )

        OrderStatusHistory.objects.create(
            order=order,
            status_from="",
            status_to=OrderStatus.PENDING_PAYMENT,
            changed_by=None,
            comment="Заказ создан",
            is_automatic=True,
        )

        return order

    @staticmethod
    def _generate_order_number(seller: "Seller") -> str:
        """
        SELECT FOR UPDATE блокирует строку Seller до конца транзакции.
        Другие параллельные checkout у того же продавца ждут; для разных
        продавцов блокировки независимы. Работает только внутри
        @transaction.atomic — perform_checkout уже обёрнут.
        """
        Seller.objects.select_for_update().filter(pk=seller.pk).first()
        year = timezone.now().year
        prefix = seller.order_prefix
        count = Order.objects.filter(
            seller=seller,
            number__startswith=f"BX-{prefix}-{year}-",
        ).count()
        return f"BX-{prefix}-{year}-{count + 1:06d}"

    @staticmethod
    def _reserve_stock(
        product: "Product",
        warehouse: "Warehouse",
        quantity: int,
    ) -> None:
        """
        get_or_create защищает от phantom — если записи нет,
        создаётся с quantity=0 и резервом на quantity.
        """
        stock, _ = ProductStock.objects.get_or_create(
            product=product,
            warehouse=warehouse,
            defaults={"quantity": 0, "reserved_quantity": 0},
        )
        stock.reserved_quantity += quantity
        stock.save(update_fields=["reserved_quantity", "updated_at"])

    @staticmethod
    def _clear_cart(user: "User") -> None:
        CartItem.objects.filter(cart__user=user).delete()
