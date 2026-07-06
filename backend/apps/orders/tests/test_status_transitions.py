"""
Unit-тесты валидатора переходов статусов (физический цикл товара).

Проверяют оба графа (stock, made_to_order) — разрешённые,
запрещённые и терминальные переходы. Оплата не входит в этот
граф — это отдельная ось PaymentStatus.
"""

from django.test import SimpleTestCase

from apps.orders.models import OrderStatus
from apps.orders.services.status_transitions import (
    get_allowed_transitions,
    is_transition_allowed,
)


class StatusTransitionsTestCase(SimpleTestCase):
    """SimpleTestCase — БД не нужна, только чистая логика графов."""

    def test_stock_created_to_assembling_allowed(self) -> None:
        self.assertTrue(is_transition_allowed(OrderStatus.CREATED, OrderStatus.ASSEMBLING, "stock"))

    def test_stock_created_to_cancelled_allowed(self) -> None:
        self.assertTrue(is_transition_allowed(OrderStatus.CREATED, OrderStatus.CANCELLED, "stock"))

    def test_stock_skip_step_forbidden(self) -> None:
        """Нельзя перескочить с created сразу на shipped."""
        self.assertFalse(is_transition_allowed(OrderStatus.CREATED, OrderStatus.SHIPPED, "stock"))

    def test_stock_cancel_after_shipped_forbidden(self) -> None:
        """После отгрузки отмена запрещена (товар в пути к клиенту)."""
        self.assertFalse(is_transition_allowed(OrderStatus.SHIPPED, OrderStatus.CANCELLED, "stock"))

    def test_made_to_order_created_to_in_production_allowed(self) -> None:
        self.assertTrue(
            is_transition_allowed(OrderStatus.CREATED, OrderStatus.IN_PRODUCTION, "made_to_order")
        )

    def test_made_to_order_created_to_assembling_forbidden(self) -> None:
        """Made-to-order обязан пройти производство перед сборкой."""
        self.assertFalse(
            is_transition_allowed(OrderStatus.CREATED, OrderStatus.ASSEMBLING, "made_to_order")
        )

    def test_delivered_is_terminal(self) -> None:
        """Из delivered никуда нельзя — терминальное состояние."""
        self.assertEqual(get_allowed_transitions(OrderStatus.DELIVERED, "stock"), set())
        self.assertEqual(get_allowed_transitions(OrderStatus.DELIVERED, "made_to_order"), set())

    def test_allowed_transitions_returns_correct_set(self) -> None:
        """Правильный набор следующих статусов для created stock."""
        transitions = get_allowed_transitions(OrderStatus.CREATED, "stock")
        self.assertEqual(transitions, {OrderStatus.ASSEMBLING, OrderStatus.CANCELLED})
