"""
Модели корзины и избранного пользователя.

Cart / CartItem — «хочу купить сейчас». Модель складского резерва не
хранит: резерв товара происходит только в момент оформления заказа
(см. Order, Слой 4). Корзина — это черновик пользователя.

Favorite — «хочу купить когда-нибудь». Долгосрочное хранилище желаний.

По решению проекта:
- Корзина создаётся лениво: не при регистрации, а при первом
  добавлении товара (через CartManager.get_or_create_for_user()).
- Один пользователь — одна корзина (гарантия через OneToOneField
  и уникальный индекс на user_id в БД).
- Цена в CartItem не сохраняется: всегда берётся актуальная из
  Product.get_effective_price(), клиент показывает её как есть.
- Неактивные товары остаются в корзине помеченными "недоступен";
  автоматическая очистка не производится, пользователь удаляет вручную.
"""

from typing import TYPE_CHECKING, ClassVar

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from apps.users.models import User


class Favorite(models.Model):
    """
    Товар, отмеченный пользователем как избранный.

    Один товар у одного пользователя может быть в избранном
    максимум один раз - контролируется UniqueConstraint.

    Не влияет на остатки и заказы. При деактивации товара
    (product.is_active=False) запись остаётся в БД, но не
    показывается покупателю в списке избранного.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Пользователь",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        verbose_name="Товар",
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Добавлено",
    )

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        ordering: ClassVar[list[str]] = ["-added_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_product_favorite",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.product}"


class CartManager(models.Manager["Cart"]):
    """
    Менеджер корзины.

    Инкапсулирует правило "один пользователь — одна корзина, создаётся лениво".
    Views вызывают get_or_create_for_user вместо прямого get_or_create,
    чтобы вся логика инициализации корзины жила в одном месте.
    """

    def get_or_create_for_user(self, user: "User") -> "Cart":
        """
        Вернуть корзину пользователя или создать новую пустую.

        Использует Django-стандартный get_or_create: если параллельно
        два запроса от одного пользователя одновременно попадут в
        момент когда корзины нет — уникальный индекс на user_id
        поймает второй попыткой, get_or_create внутри обработает
        IntegrityError и вернёт существующую запись. Без этого
        могли бы получить дубли на плохой сети (клиент ретраит).
        """
        cart, _ = self.get_or_create(user=user)
        return cart


class Cart(models.Model):
    """
    Корзина пользователя.

    Одна на пользователя (OneToOneField), создаётся лениво при первом
    добавлении товара. Не удаляется при checkout — очищается содержимое
    (CartItem), сама Cart остаётся для последующих покупок.

    updated_at обновляется только при сохранении Cart. Изменение
    CartItem само по себе не двигает updated_at. Views вызывают
    cart.save(update_fields=["updated_at"]) после изменений позиций,
    чтобы клиент видел актуальное время последней активности.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создана",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлена",
    )

    objects: ClassVar[CartManager] = CartManager()

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

    def __str__(self) -> str:
        return f"Корзина {self.user}"


class CartItem(models.Model):
    """
    Позиция в корзине: конкретный товар с количеством.

    Уникальный индекс (cart, product) гарантирует одну строку на товар
    в одной корзине. Повторное добавление того же товара увеличивает
    quantity, не создаёт дубли.

    Цена не сохраняется: при сериализации берётся актуальная из Product.
    Такой подход прозрачен для пользователя — что видит на карточке
    товара, то же увидит в корзине.
    """

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Корзина",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        verbose_name="Товар",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="Количество",
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Добавлено",
    )

    class Meta:
        verbose_name = "Позиция корзины"
        verbose_name_plural = "Позиции корзины"
        ordering: ClassVar[list[str]] = ["-added_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_cart_product",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity}"
