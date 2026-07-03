"""
Unit-тесты валидатора переходов статусов.

Проверяют оба графа (stock, made_to_order) — все разрешённые,
запрещённые и терминальные состояния.
"""

from django.test import SimpleTestCase

from apps.orders.models import OrderStatus
from apps.orders.services.status_transitions import (
    get_allowed_transitions,
    is_transition_allowed,
)


class StatusTransitionsTestCase(SimpleTestCase):
    """
    SimpleTestCase, а не TestCase — не нужна БД, только чистая логика.
    Быстрее и не создаёт лишних транзакций.
    """

    def test_stock_pending_to_paid_allowed(self) -> None:
        self.assertTrue(
            is_transition_allowed(OrderStatus.PENDING_PAYMENT, OrderStatus.PAID, "stock")
        )

    def test_stock_pending_to_cancelled_allowed(self) -> None:
        self.assertTrue(
            is_transition_allowed(OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED, "stock")
        )

    def test_stock_skip_step_forbidden(self) -> None:
        """Нельзя перескочить с pending_payment сразу на shipped."""
        self.assertFalse(
            is_transition_allowed(OrderStatus.PENDING_PAYMENT, OrderStatus.SHIPPED, "stock")
        )

    def test_stock_cancel_after_shipped_forbidden(self) -> None:
        """После отгрузки отмена запрещена (уже в пути к клиенту)."""
        self.assertFalse(is_transition_allowed(OrderStatus.SHIPPED, OrderStatus.CANCELLED, "stock"))

    def test_made_to_order_paid_to_in_production_allowed(self) -> None:
        self.assertTrue(
            is_transition_allowed(OrderStatus.PAID, OrderStatus.IN_PRODUCTION, "made_to_order")
        )

    def test_made_to_order_paid_to_assembling_forbidden(self) -> None:
        """Made-to-order обязан пройти производство перед сборкой."""
        self.assertFalse(
            is_transition_allowed(OrderStatus.PAID, OrderStatus.ASSEMBLING, "made_to_order")
        )

    def test_delivered_is_terminal(self) -> None:
        """Из delivered никуда нельзя — терминальное состояние."""
        self.assertEqual(get_allowed_transitions(OrderStatus.DELIVERED, "stock"), set())
        self.assertEqual(get_allowed_transitions(OrderStatus.DELIVERED, "made_to_order"), set())

    def test_allowed_transitions_returns_correct_set(self) -> None:
        """Правильный набор следующих статусов для paid stock."""
        transitions = get_allowed_transitions(OrderStatus.PAID, "stock")
        self.assertEqual(transitions, {OrderStatus.ASSEMBLING, OrderStatus.CANCELLED})
