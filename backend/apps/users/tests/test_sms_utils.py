"""
Тесты утилит SMS-аутентификации.

Проверяем генерацию кодов, хранение в Redis и rate limiting.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.users.api.v1.utils import (
    delete_sms_code,
    generate_sms_code,
    get_attempts,
    get_sms_code,
    increment_attempts,
    increment_rate_phone,
    is_rate_limited_by_phone,
    reset_attempts,
    save_sms_code,
)


class GenerateSmsCodeTests(TestCase):
    """Тесты генерации кода подтверждения."""

    def test_code_is_four_digits(self):
        """Код всегда состоит из 4 символов."""
        for _ in range(100):
            code = generate_sms_code()
            self.assertEqual(len(code), 4)

    def test_code_is_all_digits(self):
        """Код состоит только из цифр."""
        for _ in range(100):
            code = generate_sms_code()
            self.assertTrue(code.isdigit())

    def test_leading_zeros_preserved(self):
        """
        Среди многих генераций встречаются коды с ведущим нулём.
        Проверяем, что zfill работает и код не превращается в число.
        """
        codes = [generate_sms_code() for _ in range(1000)]
        # Хотя бы один код из 1000 должен начинаться с '0'
        # (вероятность что ни одного — ничтожна)
        has_leading_zero = any(code[0] == "0" for code in codes)
        self.assertTrue(has_leading_zero)


class SmsCodeStorageTests(TestCase):
    """Тесты хранения кода в Redis."""

    def setUp(self):
        """Перед каждым тестом чистим кеш, чтобы тесты не влияли друг на друга."""
        cache.clear()

    def test_save_and_get_code(self):
        """Сохранённый код можно прочитать обратно."""
        phone = "+79991112233"
        save_sms_code(phone, "1234")
        self.assertEqual(get_sms_code(phone), "1234")

    def test_get_nonexistent_code_returns_none(self):
        """Для номера без кода возвращается None."""
        self.assertIsNone(get_sms_code("+79990000000"))

    def test_delete_code(self):
        """После удаления код больше не доступен."""
        phone = "+79991112233"
        save_sms_code(phone, "1234")
        delete_sms_code(phone)
        self.assertIsNone(get_sms_code(phone))


class RateLimitTests(TestCase):
    """Тесты ограничения частоты запросов по номеру."""

    def setUp(self):
        cache.clear()

    def test_not_limited_initially(self):
        """Изначально номер не ограничен."""
        self.assertFalse(is_rate_limited_by_phone("+79991112233"))

    def test_limited_after_increment(self):
        """После одного запроса номер ограничен (лимит = 1/мин)."""
        phone = "+79991112233"
        increment_rate_phone(phone)
        self.assertTrue(is_rate_limited_by_phone(phone))


class AttemptsTests(TestCase):
    """Тесты счётчика попыток ввода кода."""

    def setUp(self):
        cache.clear()

    def test_attempts_start_at_zero(self):
        """Изначально попыток ноль."""
        self.assertEqual(get_attempts("+79991112233"), 0)

    def test_increment_attempts(self):
        """Счётчик увеличивается на каждый вызов."""
        phone = "+79991112233"
        self.assertEqual(increment_attempts(phone), 1)
        self.assertEqual(increment_attempts(phone), 2)
        self.assertEqual(increment_attempts(phone), 3)

    def test_reset_attempts(self):
        """После сброса счётчик обнуляется."""
        phone = "+79991112233"
        increment_attempts(phone)
        increment_attempts(phone)
        reset_attempts(phone)
        self.assertEqual(get_attempts(phone), 0)
