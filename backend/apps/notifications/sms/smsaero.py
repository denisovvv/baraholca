"""
SMS Aero provider — отправка SMS через сервис smsaero.ru.

REST API v2, авторизация HTTP Basic Auth (email + API-ключ).
Документация: https://smsaero.ru/integration/documentation/api/

Поддерживает два режима через настройку SMSAERO_TEST_MODE:
- test (True):  endpoint /v2/sms/testsend — имитация, SMS не уходит,
                деньги не списываются (для отладки интеграции)
- боевой (False): endpoint /v2/sms/send — реальная отправка
"""

import logging

import requests
from django.conf import settings

from apps.notifications.sms.base import SmsProvider, SmsProviderError

logger = logging.getLogger(__name__)

# Endpoints SMS Aero API v2.
SMSAERO_SEND_URL = "https://gate.smsaero.ru/v2/sms/send"
SMSAERO_TEST_SEND_URL = "https://gate.smsaero.ru/v2/sms/testsend"
# Таймаут запроса к внешнему сервису, секунды.
REQUEST_TIMEOUT = 10
# Успешный HTTP-статус.
HTTP_OK = 200


class SmsAeroNetworkError(SmsProviderError):
    """Ошибка сети при обращении к SMS Aero."""

    def __init__(self) -> None:
        super().__init__("SMS Aero: ошибка сети при отправке")


class SmsAeroHttpError(SmsProviderError):
    """SMS Aero вернул не-200 HTTP-статус."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"SMS Aero: HTTP-статус {status_code}")


class SmsAeroRejectedError(SmsProviderError):
    """SMS Aero отклонил отправку (success=false)."""

    def __init__(self, message: str) -> None:
        super().__init__(f"SMS Aero отклонил отправку: {message}")


class SmsAeroProvider(SmsProvider):
    """
    Отправка SMS через SMS Aero.

    Учётные данные (email, API-ключ, подпись) берутся из настроек,
    читаемых из переменных окружения (.env). Сам код НЕ логируется
    (правило безопасности) — только факт отправки и статус.

    Режим (тестовый/боевой) выбирается настройкой SMSAERO_TEST_MODE.
    """

    def __init__(self) -> None:
        self.email: str = getattr(settings, "SMSAERO_EMAIL", "")
        self.api_key: str = getattr(settings, "SMSAERO_API_KEY", "")
        self.sign: str = getattr(settings, "SMSAERO_SIGN", "SMS Aero")
        self.test_mode: bool = getattr(settings, "SMSAERO_TEST_MODE", True)

    def send(self, phone: str, code: str) -> bool:
        """
        Отправить SMS с кодом на номер через SMS Aero.

        Возвращает True при успехе. При ошибке сети/HTTP/отказа
        логирует факт (без кода) и выбрасывает наследника
        SmsProviderError.
        """
        url = SMSAERO_TEST_SEND_URL if self.test_mode else SMSAERO_SEND_URL
        # SMS Aero принимает номер без "+" и нецифровых символов
        # (в БД номера хранятся как "+7XXXXXXXXXX").
        normalized_phone = "".join(ch for ch in phone if ch.isdigit())
        params = {
            "number": normalized_phone,
            "text": f"Ваш код подтверждения: {code}",
            "sign": self.sign,
        }
        try:
            response = requests.get(
                url,
                params=params,
                auth=(self.email, self.api_key),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException:
            logger.exception("SMS Aero request failed for %s", phone)
            raise SmsAeroNetworkError from None

        if response.status_code != HTTP_OK:
            logger.error("SMS Aero HTTP %s for %s", response.status_code, phone)
            raise SmsAeroHttpError(response.status_code)

        data = response.json()
        if not data.get("success"):
            message = data.get("message", "unknown error")
            logger.error("SMS Aero rejected send to %s: %s", phone, message)
            raise SmsAeroRejectedError(message)

        mode = "test" if self.test_mode else "real"
        logger.info("SMS sent via SMS Aero (%s) to %s", mode, phone)
        return True
