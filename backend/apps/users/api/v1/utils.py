"""
Утилиты для SMS-аутентификации.

Генерация кодов, работа с Redis-кешем:
хранение кодов, rate limiting.
"""

import re
import secrets

from django.core.cache import cache
from rest_framework.exceptions import ValidationError

# Время жизни кода
SMS_CODE_TTL = 300  # 5 минут

# Rate limiting — по номеру телефона
SMS_RATE_PHONE_TTL = 60   # окно 60 секунд
SMS_RATE_PHONE_LIMIT = 1  # не более 1 запроса в окне

# Rate limiting — по IP-адресу
SMS_RATE_IP_TTL = 3600   # окно 1 час
SMS_RATE_IP_LIMIT = 5    # не более 5 запросов в окне


def generate_sms_code() -> str:
    """
    Генерирует 4-значный код подтверждения.
    """
    return str(secrets.randbelow(10000)).zfill(4)


def _phone_code_key(phone: str) -> str:
    return f'sms_code:{phone}'


def _rate_phone_key(phone: str) -> str:
    return f'sms_rate_phone:{phone}'


def _rate_ip_key(ip: str) -> str:
    return f'sms_rate_ip:{ip}'


def save_sms_code(phone: str, code: str) -> None:
    """
    Сохраняет код подтверждения в Redis с TTL.
    """
    cache.set(_phone_code_key(phone), code, timeout=SMS_CODE_TTL)


def get_sms_code(phone: str) -> str | None:
    """
    Возвращает код из Redis или None если истёк/не существует.
    """
    return cache.get(_phone_code_key(phone))


def delete_sms_code(phone: str) -> None:
    """
    Удаляет код из Redis после успешной проверки.
    """
    cache.delete(_phone_code_key(phone))


def is_rate_limited_by_phone(phone: str) -> bool:
    """
    Проверяет rate limit по номеру телефона.
    """
    key = _rate_phone_key(phone)
    count = cache.get(key, 0)
    return count >= SMS_RATE_PHONE_LIMIT


def is_rate_limited_by_ip(ip: str) -> bool:
    """
    Проверяет rate limit по IP-адресу.
    """
    key = _rate_ip_key(ip)
    count = cache.get(key, 0)
    return count >= SMS_RATE_IP_LIMIT


def increment_rate_phone(phone: str) -> None:
    """
    Увеличивает счётчик запросов по номеру телефона.
    """
    key = _rate_phone_key(phone)
    if cache.get(key) is None:
        cache.set(key, 1, timeout=SMS_RATE_PHONE_TTL)
    else:
        cache.incr(key)


def increment_rate_ip(ip: str) -> None:
    """
    Увеличивает счётчик запросов по IP-адресу.
    """
    key = _rate_ip_key(ip)
    if cache.get(key) is None:
        cache.set(key, 1, timeout=SMS_RATE_IP_TTL)
    else:
        cache.incr(key)


def get_client_ip(request) -> str:
    """
    Извлекает IP-адрес клиента из запроса.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        # X-Forwarded-For может содержать цепочку IP: "client, proxy1, proxy2"
        # Берём первый — это реальный клиент
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')

SMS_MAX_ATTEMPTS = 5


def _attempts_key(phone: str) -> str:
    return f'sms_attempts:{phone}'


def get_attempts(phone: str) -> int:
    return cache.get(_attempts_key(phone), 0)


def increment_attempts(phone: str) -> int:
    """
    Увеличивает счётчик попыток ввода кода.
    """
    key = _attempts_key(phone)
    if cache.get(key) is None:
        cache.set(key, 1, timeout=SMS_CODE_TTL)
        return 1
    return cache.incr(key)


def reset_attempts(phone: str) -> None:
    cache.delete(_attempts_key(phone))

def normalize_phone(value: str) -> str:
    """
    Нормализует номер телефона к формату +7XXXXXXXXXX.
    """
    digits = re.sub(r'\D', '', value)

    if len(digits) == 11 and digits[0] in ('7', '8'):
        digits = '7' + digits[1:]
    else:
        raise ValidationError(
            'Введите корректный номер телефона в формате +7XXXXXXXXXX'
        )

    return '+' + digits
