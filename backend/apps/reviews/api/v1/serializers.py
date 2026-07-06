"""
Сериализаторы API отзывов.

ReviewReadSerializer — отдача отзыва (публично, с обезличенным автором).
ReviewCreateSerializer — создание с проверкой "товар куплен и доставлен".
ReviewUpdateSerializer — редактирование своего отзыва (product неизменяем).
"""

from typing import Any, ClassVar

from rest_framework import serializers

from apps.orders.models import OrderItem, OrderStatus
from apps.reviews.models import Review


class ReviewReadSerializer(serializers.ModelSerializer):
    """
    Отзыв для публичного показа на карточке товара.

    Автор обезличен: "Иван П." (имя + первая буква фамилии) — баланс
    приватности и доверия. Телефон и полное имя не раскрываются.
    """

    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields: ClassVar[list[str]] = [
            "id",
            "author_name",
            "rating",
            "text",
            "created_at",
            "updated_at",
        ]

    def get_author_name(self, obj: Review) -> str:
        """Собрать обезличенное имя автора: 'Иван П.'."""
        first = obj.user.first_name or "Аноним"
        last = obj.user.last_name
        if last:
            return f"{first} {last[0]}."
        return first


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Создание отзыва.

    Проверки:
    - товар куплен и заказ доставлен (OrderStatus.DELIVERED)
    - пользователь ещё не оставлял отзыв на этот товар

    user не в полях ввода — берётся из request.user во view,
    чтобы нельзя было оставить отзыв от чужого имени.
    """

    class Meta:
        model = Review
        fields: ClassVar[list[str]] = ["product", "rating", "text"]

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        request = self.context["request"]
        user = request.user
        product = data["product"]

        has_delivered = OrderItem.objects.filter(
            order__user=user,
            order__status=OrderStatus.DELIVERED,
            product=product,
        ).exists()
        if not has_delivered:
            raise serializers.ValidationError(
                {"product": "Отзыв можно оставить только на полученный товар."}
            )

        already_reviewed = Review.objects.filter(user=user, product=product).exists()
        if already_reviewed:
            raise serializers.ValidationError({"product": "Вы уже оставили отзыв на этот товар."})

        return data


class ReviewUpdateSerializer(serializers.ModelSerializer):
    """
    Редактирование своего отзыва.

    Менять можно только rating и text. product и user неизменяемы —
    нельзя переназначить отзыв на другой товар.
    """

    class Meta:
        model = Review
        fields: ClassVar[list[str]] = ["rating", "text"]
