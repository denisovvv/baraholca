"""
Сериализаторы для API пользователей.
UserSerializer — представление профиля пользователя для мобильного приложения.
Скрывает все внутренние и серверные поля.
"""

from typing import ClassVar

from rest_framework import serializers

from apps.users.api.v1.utils import normalize_phone
from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Профиль пользователя для мобильного приложения.
    """

    class Meta:
        model = User
        fields: ClassVar[list[str]] = [
            "id",
            "phone",
            "first_name",
            "last_name",
            "phone_verified",
        ]
        read_only_fields: ClassVar[list[str]] = [
            "id",
            "phone",
            "phone_verified",
        ]


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для обновления профиля пользователя.
    """

    class Meta:
        model = User
        fields: ClassVar[list[str]] = [
            "first_name",
            "last_name",
        ]


class PhoneRequestSerializer(serializers.Serializer):
    """
    Сериализатор для запроса SMS-кода.
    """

    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)


class SmsVerifySerializer(serializers.Serializer):
    """
    Сериализатор для проверки SMS-кода.
    """

    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=4, min_length=4)

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)

    def validate_code(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("Код должен состоять из цифр")
        return value
