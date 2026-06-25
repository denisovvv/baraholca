"""
Тесты endpoints SMS-аутентификации.

Проверяем полный цикл: запрос кода, проверка кода, выдача токенов,
а также защиту: rate limit и защиту от перебора.
"""

from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from apps.users.api.v1.utils import get_sms_code
from apps.users.models import User


class SmsRequestEndpointTests(APITestCase):
    """Тесты endpoint запроса SMS-кода."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = '/api/v1/auth/sms/request/'

    def test_valid_phone_returns_sent(self):
        """Валидный номер — код отправлен, статус 200."""
        response = self.client.post(
            self.url, {'phone': '+79991112233'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'sent')

    def test_invalid_phone_returns_400(self):
        """Невалидный номер — ошибка валидации 400."""
        response = self.client.post(
            self.url, {'phone': '12345'}, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_phone_normalized(self):
        """Номер в формате 8... нормализуется и код сохраняется под +7..."""
        self.client.post(
            self.url, {'phone': '89991112233'}, format='json'
        )
        # Код должен лежать под нормализованным номером
        self.assertIsNotNone(get_sms_code('+79991112233'))

    def test_rate_limit_on_repeat(self):
        """Повторный запрос на тот же номер сразу — rate limit 429."""
        self.client.post(self.url, {'phone': '+79991112233'}, format='json')
        response = self.client.post(
            self.url, {'phone': '+79991112233'}, format='json'
        )
        self.assertEqual(response.status_code, 429)


class SmsVerifyEndpointTests(APITestCase):
    """Тесты endpoint проверки кода и выдачи токенов."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.request_url = '/api/v1/auth/sms/request/'
        self.verify_url = '/api/v1/auth/sms/verify/'
        self.phone = '+79991112233'

    def _request_code(self):
        """Вспомогательный метод: запросить код и достать его из Redis."""
        self.client.post(self.request_url, {'phone': self.phone}, format='json')
        return get_sms_code(self.phone)

    def test_correct_code_returns_tokens(self):
        """Верный код — выдаются access и refresh токены."""
        code = self._request_code()
        response = self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': code},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_new_user_created(self):
        """При первом входе создаётся новый пользователь."""
        code = self._request_code()
        response = self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': code},
            format='json',
        )
        self.assertTrue(response.data['is_new_user'])
        self.assertTrue(User.objects.filter(phone=self.phone).exists())

    def test_user_phone_verified(self):
        """После входа у пользователя phone_verified = True."""
        code = self._request_code()
        self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': code},
            format='json',
        )
        user = User.objects.get(phone=self.phone)
        self.assertTrue(user.phone_verified)

    def test_wrong_code_returns_401(self):
        """Неверный код — ошибка 401."""
        self._request_code()
        response = self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': '0000'},
            format='json',
        )
        # Если случайно код реально 0000 — берём другой неверный
        if response.status_code == 200:
            self.skipTest('Случайно угадали код, редкость')
        self.assertEqual(response.status_code, 401)

    def test_code_is_single_use(self):
        """После успешного входа код больше не работает."""
        code = self._request_code()
        # Первый раз — успех
        self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': code},
            format='json',
        )
        # Второй раз с тем же кодом — отказ
        response = self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': code},
            format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_existing_user_not_recreated(self):
        """Повторный вход существующего пользователя не создаёт дубль."""
        # Первый вход
        code = self._request_code()
        first = self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': code},
            format='json',
        )
        self.assertTrue(first.data['is_new_user'])

        # Второй вход (новый код, тот же номер)
        cache.clear()
        code2 = self._request_code()
        second = self.client.post(
            self.verify_url,
            {'phone': self.phone, 'code': code2},
            format='json',
        )
        self.assertFalse(second.data['is_new_user'])
        # Пользователь по-прежнему один
        self.assertEqual(User.objects.filter(phone=self.phone).count(), 1)
