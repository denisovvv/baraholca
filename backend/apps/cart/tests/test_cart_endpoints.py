"""
Тесты API корзины (/api/v1/cart/).

Покрывают три endpoint-а:
  GET,    /cart/                          — получить корзину
  DELETE, /cart/                          — очистить корзину
  GET,    /cart/count/                    — счётчик
  PUT,    /cart/items/<product_id>/       — добавить/обновить (idempotent)
  DELETE, /cart/items/<product_id>/       — удалить (idempotent)

Аутентификация — реальным JWT через заголовок Authorization,
полная цепочка RefreshToken.for_user → JWTAuthentication.

setUpTestData создаёт общие тестовые данные один раз для класса:
двух пользователей, три товара (активный, неактивный, снятый с продажи),
seller и категорию.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product
from apps.sellers.models import Seller

User = get_user_model()


class CartEndpointsTests(APITestCase):
    """Тесты /api/v1/cart/ — чтение, очистка, счётчик, работа с позициями."""

    @classmethod
    def setUpTestData(cls) -> None:
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
        self.cart_url = "/api/v1/cart/"
        self.count_url = "/api/v1/cart/count/"

    def _auth(self, user: User) -> None:
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def _item_url(self, product_id: int) -> str:
        return f"/api/v1/cart/items/{product_id}/"

    def test_get_without_token_returns_unauthorized(self) -> None:
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")

    def test_get_empty_cart_when_no_cart_exists(self) -> None:
        self._auth(self.user)
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["total_quantity"], 0)
        self.assertIsNone(response.data["updated_at"])
        self.assertFalse(Cart.objects.filter(user=self.user).exists())

    def test_get_returns_items_with_nested_product(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=2)

        self._auth(self.user)
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)

        item = response.data["items"][0]
        self.assertIn("product", item)
        self.assertEqual(item["product"]["id"], self.active_product.id)
        self.assertEqual(item["product"]["name_short"], "Кружка")
        self.assertEqual(item["quantity"], 2)
        self.assertIn("added_at", item)

    def test_get_is_available_flag_reflects_product_status(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=1)
        CartItem.objects.create(cart=cart, product=self.inactive_product, quantity=1)
        CartItem.objects.create(cart=cart, product=self.unavailable_product, quantity=1)

        self._auth(self.user)
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 3)

        availability = {
            item["product"]["id"]: item["is_available"] for item in response.data["items"]
        }
        self.assertTrue(availability[self.active_product.id])
        self.assertFalse(availability[self.inactive_product.id])
        self.assertFalse(availability[self.unavailable_product.id])

    def test_get_total_quantity_is_sum_of_all_items(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=2)
        CartItem.objects.create(cart=cart, product=self.inactive_product, quantity=3)

        self._auth(self.user)
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_quantity"], 5)

    def test_delete_cart_without_token_returns_unauthorized(self) -> None:
        response = self.client.delete(self.cart_url)
        self.assertEqual(response.status_code, 401)

    def test_delete_cart_clears_items_and_keeps_cart(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=2)

        self._auth(self.user)
        response = self.client.delete(self.cart_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(CartItem.objects.filter(cart=cart).count(), 0)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_delete_cart_is_idempotent_when_no_cart_exists(self) -> None:
        self.assertFalse(Cart.objects.filter(user=self.user).exists())

        self._auth(self.user)
        response = self.client.delete(self.cart_url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Cart.objects.filter(user=self.user).exists())

    def test_count_without_token_returns_unauthorized(self) -> None:
        response = self.client.get(self.count_url)
        self.assertEqual(response.status_code, 401)

    def test_count_returns_zeros_when_no_cart(self) -> None:
        self._auth(self.user)
        response = self.client.get(self.count_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"items_count": 0, "total_quantity": 0})

    def test_count_returns_both_metrics(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=2)
        CartItem.objects.create(cart=cart, product=self.inactive_product, quantity=3)
        CartItem.objects.create(cart=cart, product=self.unavailable_product, quantity=2)

        self._auth(self.user)
        response = self.client.get(self.count_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"items_count": 3, "total_quantity": 7})

    def test_put_item_without_token_returns_unauthorized(self) -> None:
        response = self.client.put(
            self._item_url(self.active_product.id),
            {"quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Cart.objects.filter(user=self.user).exists())

    def test_put_first_item_creates_cart_and_item(self) -> None:
        self.assertFalse(Cart.objects.filter(user=self.user).exists())

        self._auth(self.user)
        response = self.client.put(
            self._item_url(self.active_product.id),
            {"quantity": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        cart = Cart.objects.get(user=self.user)
        item = CartItem.objects.get(cart=cart, product=self.active_product)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["total_quantity"], 2)

    def test_put_existing_item_replaces_quantity(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=1)

        self._auth(self.user)
        response = self.client.put(
            self._item_url(self.active_product.id),
            {"quantity": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        item = CartItem.objects.get(cart=cart, product=self.active_product)
        self.assertEqual(item.quantity, 5)

    def test_put_nonexistent_product_returns_product_not_found(self) -> None:
        self._auth(self.user)
        response = self.client.put(
            self._item_url(999_999),
            {"quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "product_not_found")

    def test_put_inactive_product_returns_product_unavailable(self) -> None:
        self._auth(self.user)
        response = self.client.put(
            self._item_url(self.inactive_product.id),
            {"quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "product_unavailable")
        self.assertFalse(
            CartItem.objects.filter(cart__user=self.user, product=self.inactive_product).exists()
        )

    def test_put_unavailable_for_sale_product_returns_product_unavailable(self) -> None:
        self._auth(self.user)
        response = self.client.put(
            self._item_url(self.unavailable_product.id),
            {"quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"]["code"], "product_unavailable")

    def test_put_quantity_zero_removes_item_and_returns_cart(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=3)

        self._auth(self.user)
        response = self.client.put(
            self._item_url(self.active_product.id),
            {"quantity": 0},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CartItem.objects.filter(cart=cart, product=self.active_product).exists())
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["total_quantity"], 0)

    def test_put_negative_quantity_returns_validation_error(self) -> None:
        self._auth(self.user)
        response = self.client.put(
            self._item_url(self.active_product.id),
            {"quantity": -1},
            format="json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.data)
        self.assertFalse(
            CartItem.objects.filter(cart__user=self.user, product=self.active_product).exists()
        )

    def test_delete_item_without_token_returns_unauthorized(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=1)

        response = self.client.delete(self._item_url(self.active_product.id))
        self.assertEqual(response.status_code, 401)
        self.assertTrue(CartItem.objects.filter(cart=cart, product=self.active_product).exists())

    def test_delete_existing_item_returns_204(self) -> None:
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=1)

        self._auth(self.user)
        response = self.client.delete(self._item_url(self.active_product.id))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(CartItem.objects.filter(cart=cart, product=self.active_product).exists())

    def test_delete_missing_item_is_idempotent(self) -> None:
        Cart.objects.create(user=self.user)

        self._auth(self.user)
        response = self.client.delete(self._item_url(self.active_product.id))
        self.assertEqual(response.status_code, 204)

    def test_delete_item_does_not_affect_other_user(self) -> None:
        cart_a = Cart.objects.create(user=self.user)
        cart_b = Cart.objects.create(user=self.other_user)
        CartItem.objects.create(cart=cart_a, product=self.active_product, quantity=1)
        CartItem.objects.create(cart=cart_b, product=self.active_product, quantity=1)

        self._auth(self.user)
        response = self.client.delete(self._item_url(self.active_product.id))
        self.assertEqual(response.status_code, 204)

        self.assertFalse(CartItem.objects.filter(cart=cart_a, product=self.active_product).exists())
        self.assertTrue(CartItem.objects.filter(cart=cart_b, product=self.active_product).exists())

    def test_users_see_only_their_own_carts(self) -> None:
        cart_a = Cart.objects.create(user=self.user)
        cart_b = Cart.objects.create(user=self.other_user)
        CartItem.objects.create(cart=cart_a, product=self.active_product, quantity=1)
        CartItem.objects.create(cart=cart_b, product=self.active_product, quantity=5)

        self._auth(self.user)
        response_a = self.client.get(self.cart_url)
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_a.data["total_quantity"], 1)

        self._auth(self.other_user)
        response_b = self.client.get(self.cart_url)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_b.data["total_quantity"], 5)
