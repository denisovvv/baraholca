"""
Тесты API избранного (/api/v1/favorites/).

Покрывают все четыре endpoint-а:
  GET    /favorites/               — список
  GET    /favorites/count/         — счётчик
  PUT    /favorites/<product_id>/  — добавить (идемпотентно)
  DELETE /favorites/<product_id>/  — убрать (идемпотентно)

Аутентификация — реальным JWT через заголовок Authorization,
чтобы покрыть полную цепочку: RefreshToken.for_user → JWTAuthentication.

Тестовые данные создаются через setUpTestData: один раз для всего
класса, откатываются в конце. Это ускоряет прогон и корректно
изолирует тесты друг от друга (каждый тест видит свежее состояние).
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cart.models import Favorite
from apps.catalog.models import Category, Product
from apps.sellers.models import Seller

User = get_user_model()


class FavoriteEndpointsTests(APITestCase):
    """Тесты /api/v1/favorites/ — список, счётчик, добавление, удаление."""

    @classmethod
    def setUpTestData(cls) -> None:
        """
        Создаём тестовые данные, общие для всех тестов класса.

        Два пользователя, два товара — один активный, один неактивный —
        плюс один товар, который "не в продаже" (is_available_for_sale=False),
        чтобы проверить фильтрацию списка и счётчика.
        """
        cls.user = User.objects.create(
            phone="+79991112233",
            first_name="Иван",
            last_name="Петров",
            phone_verified=True,
        )
        cls.other_user = User.objects.create(
            phone="+79994445566",
            first_name="Сергей",
            last_name="Иванов",
            phone_verified=True,
        )

        cls.seller = Seller.objects.create(
            name="ИП Иванов И.И.",
            short_name="Иванов",
            inn="123456789012",
            ogrnip="123456789012345",
            contact_phone="+79990000000",
        )
        cls.category = Category.objects.create(
            name="Посуда",
            slug="dishes",
        )

        cls.active_product = Product.objects.create(
            name_short="Кружка",
            name_full="Кружка керамическая большая",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("500.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=True,
        )
        cls.inactive_product = Product.objects.create(
            name_short="Тарелка",
            name_full="Тарелка временно снята",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("300.00"),
            product_type="stock",
            is_active=False,
            is_available_for_sale=True,
        )
        cls.unavailable_product = Product.objects.create(
            name_short="Блюдце",
            name_full="Блюдце нет в продаже",
            seller=cls.seller,
            category=cls.category,
            base_price=Decimal("100.00"),
            product_type="stock",
            is_active=True,
            is_available_for_sale=False,
        )

    def setUp(self) -> None:
        self.list_url = "/api/v1/favorites/"
        self.count_url = "/api/v1/favorites/count/"

    def _auth(self, user: User) -> None:
        """Установить в клиенте JWT-токен пользователя для последующих запросов."""
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def _detail_url(self, product_id: int) -> str:
        return f"/api/v1/favorites/{product_id}/"

    def test_list_without_token_returns_unauthorized(self) -> None:
        """Без токена — 401 с error.code = not_authenticated."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")

    def test_list_empty_when_no_favorites(self) -> None:
        """Аутентифицированный пользователь без избранного — 200 и пустой список."""
        self._auth(self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_list_returns_favorites_with_nested_product(self) -> None:
        """
        В списке — записи с развёрнутым Product внутри.
        Проверяем что product вложен и содержит ключевые поля из ProductListSerializer.
        """
        Favorite.objects.create(user=self.user, product=self.active_product)

        self._auth(self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        item = response.data[0]
        self.assertIn("added_at", item)
        self.assertIn("product", item)
        product = item["product"]
        self.assertEqual(product["id"], self.active_product.id)
        self.assertEqual(product["name_short"], "Кружка")
        self.assertIn("base_price", product)
        self.assertIn("effective_price", product)

    def test_list_filters_out_inactive_products(self) -> None:
        """
        Неактивные и снятые с продажи товары не показываются в списке.
        Даже если запись Favorite есть в БД — клиент не видит её.
        """
        Favorite.objects.create(user=self.user, product=self.active_product)
        Favorite.objects.create(user=self.user, product=self.inactive_product)
        Favorite.objects.create(user=self.user, product=self.unavailable_product)

        self._auth(self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["product"]["id"], self.active_product.id)
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 3)

    def test_count_without_token_returns_unauthorized(self) -> None:
        """Без токена — 401."""
        response = self.client.get(self.count_url)
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")

    def test_count_returns_number(self) -> None:
        """Аутентифицированный клиент получает {"count": N}."""
        Favorite.objects.create(user=self.user, product=self.active_product)

        self._auth(self.user)
        response = self.client.get(self.count_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"count": 1})

    def test_count_matches_list_by_ignoring_inactive(self) -> None:
        """
        Счётчик должен быть согласован со списком.
        Если в БД 3 записи, но 2 из них — по неактивным товарам, count = 1.
        """
        Favorite.objects.create(user=self.user, product=self.active_product)
        Favorite.objects.create(user=self.user, product=self.inactive_product)
        Favorite.objects.create(user=self.user, product=self.unavailable_product)

        self._auth(self.user)
        response = self.client.get(self.count_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"count": 1})

    def test_put_without_token_returns_unauthorized(self) -> None:
        """Без токена — 401, запись не создаётся."""
        response = self.client.put(self._detail_url(self.active_product.id))
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")
        self.assertFalse(
            Favorite.objects.filter(user=self.user, product=self.active_product).exists()
        )

    def test_put_new_product_returns_201_created(self) -> None:
        """
        Первый PUT — создание записи, ответ 201 Created с телом избранного.
        Тело содержит развёрнутый product и added_at.
        """
        self._auth(self.user)
        response = self.client.put(self._detail_url(self.active_product.id))
        self.assertEqual(response.status_code, 201)
        self.assertIn("product", response.data)
        self.assertEqual(response.data["product"]["id"], self.active_product.id)
        self.assertIn("added_at", response.data)
        self.assertTrue(
            Favorite.objects.filter(user=self.user, product=self.active_product).exists()
        )

    def test_put_existing_favorite_returns_200_ok(self) -> None:
        """
        Повторный PUT — 200 OK (идемпотентно, ничего не изменилось).
        В БД по-прежнему одна запись.
        """
        Favorite.objects.create(user=self.user, product=self.active_product)

        self._auth(self.user)
        response = self.client.put(self._detail_url(self.active_product.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product"]["id"], self.active_product.id)
        self.assertEqual(
            Favorite.objects.filter(user=self.user, product=self.active_product).count(),
            1,
        )

    def test_put_nonexistent_product_returns_product_not_found(self) -> None:
        """
        PUT несуществующего product — 404 product_not_found.
        Единый контракт ошибок: {"error": {"code": "product_not_found", "message": ...}}.
        """
        self._auth(self.user)
        response = self.client.put(self._detail_url(999_999))
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "product_not_found")
        self.assertTrue(response.data["error"]["message"])

    def test_put_inactive_product_is_allowed(self) -> None:
        """
        PUT неактивного товара разрешён по решению проекта.
        Товар может быть временно скрыт продавцом, но пользователь
        всё равно может отметить его как избранное на будущее.
        В списке клиент такую запись не увидит (см. фильтрацию),
        но она есть в БД и вернётся, когда товар снова станет активным.
        """
        self._auth(self.user)
        response = self.client.put(self._detail_url(self.inactive_product.id))
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Favorite.objects.filter(user=self.user, product=self.inactive_product).exists()
        )
        list_response = self.client.get(self.list_url)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data, [])

    def test_delete_without_token_returns_unauthorized(self) -> None:
        """Без токена — 401, ничего не удаляется."""
        Favorite.objects.create(user=self.user, product=self.active_product)

        response = self.client.delete(self._detail_url(self.active_product.id))
        self.assertEqual(response.status_code, 401)
        self.assertTrue(
            Favorite.objects.filter(user=self.user, product=self.active_product).exists()
        )

    def test_delete_existing_favorite_returns_204(self) -> None:
        """DELETE существующего избранного — 204, запись исчезает из БД."""
        Favorite.objects.create(user=self.user, product=self.active_product)

        self._auth(self.user)
        response = self.client.delete(self._detail_url(self.active_product.id))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Favorite.objects.filter(user=self.user, product=self.active_product).exists()
        )

    def test_delete_missing_favorite_is_idempotent(self) -> None:
        """
        DELETE несуществующего избранного — 204, не 404.

        Идемпотентность: клиент просит "убрать" — сервер возвращает 204
        независимо от того, было ли что убирать. Клиенту не важно "было ли",
        важно что "сейчас нет".
        """
        self.assertFalse(
            Favorite.objects.filter(user=self.user, product=self.active_product).exists()
        )

        self._auth(self.user)
        response = self.client.delete(self._detail_url(self.active_product.id))
        self.assertEqual(response.status_code, 204)

    def test_delete_by_one_user_does_not_affect_other(self) -> None:
        """
        Пользователь A удалил своё избранное — избранное B не тронуто.
        Проверяет фильтрацию по request.user на уровне DELETE.
        """
        Favorite.objects.create(user=self.user, product=self.active_product)
        Favorite.objects.create(user=self.other_user, product=self.active_product)

        self._auth(self.user)
        response = self.client.delete(self._detail_url(self.active_product.id))
        self.assertEqual(response.status_code, 204)

        self.assertFalse(
            Favorite.objects.filter(user=self.user, product=self.active_product).exists()
        )
        self.assertTrue(
            Favorite.objects.filter(user=self.other_user, product=self.active_product).exists()
        )

    def test_users_see_only_their_own_favorites(self) -> None:
        """
        Два пользователя работают с /favorites/ независимо.
        User A видит только свои записи, User B — только свои.
        """
        Favorite.objects.create(user=self.user, product=self.active_product)
        Favorite.objects.create(user=self.other_user, product=self.active_product)

        self._auth(self.user)
        response_a = self.client.get(self.list_url)
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(len(response_a.data), 1)

        self._auth(self.other_user)
        response_b = self.client.get(self.list_url)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(len(response_b.data), 1)

        self.assertEqual(Favorite.objects.count(), 2)
