"""
Утилиты для SMS-аутентификации.

Генерация кодов, работа с Redis-кешем:
хранение кодов, rate limiting.

БЕЗОПАСНОСТЬ:
- Коды генерируются через secrets (криптографически стойкий RNG)
- Коды никогда не логируются
- Ключи Redis имеют TTL (автоматически удаляются)
"""

import secrets

from django.core.cache import cache


# Время жизни кода подтверждения в секундах
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

    Использует secrets.randbelow — криптографически стойкий генератор.
    Обычный random.randint НЕ подходит для кодов безопасности.

    Returns:
        Строка из 4 цифр, например '0842'. Ведущие нули сохраняются.
    """
    return str(secrets.randbelow(10000)).zfill(4)


def _phone_code_key(phone: str) -> str:
    """Ключ Redis для хранения кода по номеру телефона."""
    return f'sms_code:{phone}'


def _rate_phone_key(phone: str) -> str:
    """Ключ Redis для rate limit по номеру телефона."""
    return f'sms_rate_phone:{phone}'


def _rate_ip_key(ip: str) -> str:
    """Ключ Redis для rate limit по IP-адресу."""
    return f'sms_rate_ip:{ip}'


def save_sms_code(phone: str, code: str) -> None:
    """
    Сохраняет код подтверждения в Redis с TTL.

    Если для этого номера уже есть код — перезаписывает.
    Это нормально: пользователь мог запросить повторно.

    Args:
        phone: Номер телефона (+7XXXXXXXXXX)
        code: 4-значный код (НЕ логируется)
    """
    cache.set(_phone_code_key(phone), code, timeout=SMS_CODE_TTL)


def get_sms_code(phone: str) -> str | None:
    """
    Возвращает код из Redis или None если истёк/не существует.

    Args:
        phone: Номер телефона

    Returns:
        Код как строка ('0842') или None.
    """
    return cache.get(_phone_code_key(phone))


def delete_sms_code(phone: str) -> None:
    """
    Удаляет код из Redis после успешной проверки.

    Код должен быть одноразовым — после использования удаляем.
    """
    cache.delete(_phone_code_key(phone))


def is_rate_limited_by_phone(phone: str) -> bool:
    """
    Проверяет rate limit по номеру телефона.

    Returns:
        True если лимит превышен (нельзя отправить SMS).
        False если всё в порядке.
    """
    key = _rate_phone_key(phone)
    count = cache.get(key, 0)
    return count >= SMS_RATE_PHONE_LIMIT


def is_rate_limited_by_ip(ip: str) -> bool:
    """
    Проверяет rate limit по IP-адресу.

    Returns:
        True если лимит превышен.
        False если всё в порядке.
    """
    key = _rate_ip_key(ip)
    count = cache.get(key, 0)
    return count >= SMS_RATE_IP_LIMIT


def increment_rate_phone(phone: str) -> None:
    """
    Увеличивает счётчик запросов по номеру телефона.

    Вызывается ПОСЛЕ успешной отправки SMS.
    Если ключа нет — создаёт с TTL.
    Если ключ есть — увеличивает счётчик.
    """
    key = _rate_phone_key(phone)
    if cache.get(key) is None:
        cache.set(key, 1, timeout=SMS_RATE_PHONE_TTL)
    else:
        cache.incr(key)


def increment_rate_ip(ip: str) -> None:
    """
    Увеличивает счётчик запросов по IP-адресу.

    Вызывается ПОСЛЕ успешной отправки SMS.
    """
    key = _rate_ip_key(ip)
    if cache.get(key) is None:
        cache.set(key, 1, timeout=SMS_RATE_IP_TTL)
    else:
        cache.incr(key)


def get_client_ip(request) -> str:
    """
    Извлекает IP-адрес клиента из запроса.

    Учитывает случай, когда сервер стоит за nginx/proxy
    (заголовок X-Forwarded-For).
    На проде nginx будет передавать реальный IP в этом заголовке.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        # X-Forwarded-For может содержать цепочку IP: "client, proxy1, proxy2"
        # Берём первый — это реальный клиент
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')