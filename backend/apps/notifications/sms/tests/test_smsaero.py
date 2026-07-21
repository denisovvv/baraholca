"""
Тесты SmsAeroProvider с моком HTTP (реальные SMS не отправляются).
"""

from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from apps.notifications.sms.smsaero import (
    SmsAeroHttpError,
    SmsAeroNetworkError,
    SmsAeroProvider,
    SmsAeroRejectedError,
)


@override_settings(
    SMSAERO_EMAIL="test@example.com",
    SMSAERO_API_KEY="test_key",
    SMSAERO_SIGN="SMS Aero",
    SMSAERO_TEST_MODE=False,
)
class SmsAeroProviderTests(TestCase):
    """Тесты провайдера SMS Aero (HTTP замокан)."""

    def _mock_response(self, status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {"success": True}
        return resp

    @patch("apps.notifications.sms.smsaero.requests.get")
    def test_successful_send(self, mock_get):
        """Успешная отправка возвращает True."""
        mock_get.return_value = self._mock_response(
            json_data={"success": True, "data": {"id": 1}},
        )
        provider = SmsAeroProvider()
        result = provider.send("+79991234567", "1234")
        self.assertTrue(result)

    @patch("apps.notifications.sms.smsaero.requests.get")
    def test_phone_normalized(self, mock_get):
        """Номер очищается от + перед отправкой."""
        mock_get.return_value = self._mock_response(json_data={"success": True})
        provider = SmsAeroProvider()
        provider.send("+79991234567", "1234")
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["number"], "79991234567")

    @patch("apps.notifications.sms.smsaero.requests.get")
    def test_code_not_in_logs(self, mock_get):
        """Код НЕ логируется (правило безопасности)."""
        mock_get.return_value = self._mock_response(json_data={"success": True})
        provider = SmsAeroProvider()
        with self.assertLogs("apps.notifications.sms.smsaero", level="INFO") as logs:
            provider.send("+79991234567", "SECRET99")
        for line in logs.output:
            self.assertNotIn("SECRET99", line)

    @patch("apps.notifications.sms.smsaero.requests.get")
    def test_network_error(self, mock_get):
        """Ошибка сети → SmsAeroNetworkError."""
        mock_get.side_effect = requests.RequestException("boom")
        provider = SmsAeroProvider()
        with self.assertRaises(SmsAeroNetworkError):
            provider.send("+79991234567", "1234")

    @patch("apps.notifications.sms.smsaero.requests.get")
    def test_http_error(self, mock_get):
        """HTTP не-200 → SmsAeroHttpError."""
        mock_get.return_value = self._mock_response(status_code=403)
        provider = SmsAeroProvider()
        with self.assertRaises(SmsAeroHttpError):
            provider.send("+79991234567", "1234")

    @patch("apps.notifications.sms.smsaero.requests.get")
    def test_rejected(self, mock_get):
        """success=false → SmsAeroRejectedError."""
        mock_get.return_value = self._mock_response(
            json_data={"success": False, "message": "sign incorrect"},
        )
        provider = SmsAeroProvider()
        with self.assertRaises(SmsAeroRejectedError):
            provider.send("+79991234567", "1234")
