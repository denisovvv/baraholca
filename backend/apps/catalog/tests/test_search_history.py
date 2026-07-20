"""
Тесты истории поиска пользователя.
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import SearchQuery

User = get_user_model()


class SearchHistoryTests(APITestCase):
    """Тесты endpoints истории поиска."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create(
            phone="+79991112233",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        cls.other = User.objects.create(
            phone="+79994445566",
            first_name="Пётр",
            last_name="Сидоров",
            phone_verified=True,
        )

    def setUp(self) -> None:
        self.url = "/api/v1/catalog/search-history/"

    def _auth(self, user: User) -> None:
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def _item_url(self, query_id: int) -> str:
        return f"/api/v1/catalog/search-history/{query_id}/"

    def test_requires_authentication(self) -> None:
        """Без токена — 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_post_saves_query(self) -> None:
        """POST сохраняет запрос."""
        self._auth(self.user)
        response = self.client.post(self.url, {"query": "чехол"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["query"], "чехол")
        self.assertTrue(SearchQuery.objects.filter(user=self.user, query="чехол").exists())

    def test_post_empty_query_400(self) -> None:
        """Пустой запрос — 400."""
        self._auth(self.user)
        response = self.client.post(self.url, {"query": "  "}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_get_returns_recent_first(self) -> None:
        """GET отдаёт запросы, свежий сверху."""
        self._auth(self.user)
        SearchQuery.objects.create(user=self.user, query="старый")
        SearchQuery.objects.create(user=self.user, query="новый")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["query"], "новый")

    def test_get_deduplicates(self) -> None:
        """Дубликаты схлопываются (уникальные запросы)."""
        self._auth(self.user)
        SearchQuery.objects.create(user=self.user, query="чехол")
        SearchQuery.objects.create(user=self.user, query="кружка")
        SearchQuery.objects.create(user=self.user, query="чехол")
        response = self.client.get(self.url)
        queries = [item["query"] for item in response.data]
        # "чехол" один раз, свежий сверху
        self.assertEqual(queries.count("чехол"), 1)
        self.assertEqual(queries[0], "чехол")

    def test_get_only_own_history(self) -> None:
        """Пользователь видит только свою историю."""
        self._auth(self.user)
        SearchQuery.objects.create(user=self.user, query="мой запрос")
        SearchQuery.objects.create(user=self.other, query="чужой запрос")
        response = self.client.get(self.url)
        queries = {item["query"] for item in response.data}
        self.assertIn("мой запрос", queries)
        self.assertNotIn("чужой запрос", queries)

    def test_delete_clears_all(self) -> None:
        """DELETE очищает всю историю пользователя."""
        self._auth(self.user)
        SearchQuery.objects.create(user=self.user, query="a")
        SearchQuery.objects.create(user=self.user, query="b")
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SearchQuery.objects.filter(user=self.user).exists())

    def test_delete_one_item(self) -> None:
        """DELETE один запрос по id."""
        self._auth(self.user)
        sq = SearchQuery.objects.create(user=self.user, query="удалить меня")
        response = self.client.delete(self._item_url(sq.id))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SearchQuery.objects.filter(id=sq.id).exists())

    def test_cannot_delete_others_item(self) -> None:
        """Нельзя удалить чужой запрос — 404."""
        self._auth(self.user)
        foreign = SearchQuery.objects.create(user=self.other, query="чужой")
        response = self.client.delete(self._item_url(foreign.id))
        self.assertEqual(response.status_code, 404)
        # Чужой запрос остался
        self.assertTrue(SearchQuery.objects.filter(id=foreign.id).exists())
