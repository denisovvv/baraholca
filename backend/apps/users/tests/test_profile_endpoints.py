"""
Тесты endpoint профиля пользователя (/api/v1/users/me/).

Проверяем GET (чтение своего профиля), PATCH (обновление first_name/last_name),
защиту (только свой профиль, не чужой), контракт ошибок (пустой PATCH → 422).

Аутентификация в тестах — реальным JWT через заголовок Authorization,
чтобы покрыть полную цепочку: RefreshToken.for_user → JWTAuthentication.
"""

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


class UserMeEndpointTests(APITestCase):
    """Тесты /api/v1/users/me/ — чтение и обновление своего профиля."""

    def setUp(self) -> None:
        self.url = "/api/v1/users/me/"
        self.user = User.objects.create(
            phone="+79991112233",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )

    def _auth(self, user: User) -> None:
        """Установить в клиенте JWT-токен пользователя для последующих запросов."""
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def test_get_without_token_returns_unauthorized(self) -> None:
        """Без токена — 401 с error.code от DRF-аутентификации."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")
        self.assertTrue(response.data["error"]["message"])

    def test_get_with_token_returns_profile(self) -> None:
        """С валидным токеном — 200 и полные поля профиля."""
        self._auth(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.user.id)
        self.assertEqual(response.data["phone"], "+79991112233")
        self.assertEqual(response.data["first_name"], "Иван")
        self.assertEqual(response.data["last_name"], "Петров")
        self.assertTrue(response.data["phone_verified"])

    def test_get_does_not_expose_email(self) -> None:
        """
        Email — спящее поле, не показывается в API даже если есть в БД.
        См. решение проекта: соц-логин отложен, email не редактируется через профиль.
        """
        self.user.email = "hidden@example.com"
        self.user.save(update_fields=["email"])
        self._auth(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("email", response.data)

    def test_patch_without_token_returns_unauthorized(self) -> None:
        """PATCH без токена — 401, ничего не обновляется."""
        response = self.client.patch(
            self.url,
            {"first_name": "Пётр"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")

    def test_patch_updates_name_fields(self) -> None:
        """PATCH с валидным телом — 200, поля обновлены, ответ содержит полный профиль."""
        self._auth(self.user)
        response = self.client.patch(
            self.url,
            {"first_name": "Пётр", "last_name": "Сидоров"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], "Пётр")
        self.assertEqual(response.data["last_name"], "Сидоров")
        self.assertEqual(response.data["phone"], "+79991112233")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Пётр")
        self.assertEqual(self.user.last_name, "Сидоров")

    def test_patch_partial_updates_only_provided_fields(self) -> None:
        """
        PATCH только с одним полем — обновляет только его, остальные остаются.
        Проверяем семантику partial=True в сериализаторе.
        """
        self._auth(self.user)
        response = self.client.patch(
            self.url,
            {"first_name": "Пётр"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Пётр")
        self.assertEqual(self.user.last_name, "Петров")

    def test_patch_empty_body_returns_validation_error(self) -> None:
        """
        PATCH с пустым телом — 422 nothing_to_update.

        Пустое тело — обычно баг клиента (форма не собрала поля).
        Мы явно сообщаем об этом, чтобы не молчать no-op-ом.
        """
        self._auth(self.user)
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "nothing_to_update")
        self.assertTrue(response.data["error"]["message"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Иван")
        self.assertEqual(self.user.last_name, "Петров")

    def test_patch_ignores_readonly_phone(self) -> None:
        """
        PATCH с попыткой изменить phone — phone остаётся прежним.

        Поле phone нет в UserUpdateSerializer.fields, DRF молча его игнорирует.
        Проверяем что тело валидно (не отдаёт 422 из-за лишнего поля) и что
        phone в БД не поменялся.
        """
        self._auth(self.user)
        response = self.client.patch(
            self.url,
            {"first_name": "Пётр", "phone": "+79998887766"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Пётр")
        self.assertEqual(self.user.phone, "+79991112233")

    def test_patch_ignores_readonly_phone_verified(self) -> None:
        """
        Аналогичная проверка для phone_verified — тоже read-only через сериализатор.
        Клиент не должен иметь возможность самому "подтвердить" телефон.
        """
        self.user.phone_verified = False
        self.user.save(update_fields=["phone_verified"])

        self._auth(self.user)
        response = self.client.patch(
            self.url,
            {"first_name": "Пётр", "phone_verified": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)

    def test_two_users_isolated(self) -> None:
        """
        Два пользователя работают с /me/ независимо.

        Пользователь A обновляет свой профиль — профиль пользователя B не меняется.
        Проверяет что /me/ действительно ссылается на request.user, а не на что-то общее.
        """
        other = User.objects.create(
            phone="+79991110000",
            first_name="Сергей",
            last_name="Иванов",
            phone_verified=True,
        )

        self._auth(self.user)
        self.client.patch(
            self.url,
            {"first_name": "Пётр"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Пётр")

        other.refresh_from_db()
        self.assertEqual(other.first_name, "Сергей")
