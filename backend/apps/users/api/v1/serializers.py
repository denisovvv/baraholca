"""
Сериализаторы для API пользователей.

UserSerializer — представление профиля пользователя для мобильного приложения.
Скрывает все внутренние и серверные поля.
"""

from rest_framework import serializers

from apps.users.models import User
from apps.users.api.v1.utils import normalize_phone


class UserSerializer(serializers.ModelSerializer):
    """
    Профиль пользователя для мобильного приложения.

    Все поля только для чтения — изменение профиля идёт через
    UserUpdateSerializer на отдельном endpoint.
    """

    class Meta:
        model = User
        fields = [
            'id',
            'phone',
            'first_name',
            'last_name',
            'phone_verified',
        ]
        read_only_fields = [
            'id',
            'phone',
            'phone_verified',
        ]


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для обновления профиля пользователя.

    Разрешает изменять только имя и фамилию.
    Номер телефона меняется только через процесс смены номера
    (с подтверждением SMS на новый номер).
    """

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
        ]


class PhoneRequestSerializer(serializers.Serializer):
    """
    Сериализатор для запроса SMS-кода.

    Принимает и нормализует номер телефона.
    Приводит разные форматы к единому виду +7XXXXXXXXXX.

    Это НЕ ModelSerializer — мы не создаём объект,
    а только валидируем входящий номер.
    """

    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value: str) -> str:
        """Нормализует номер к формату +7XXXXXXXXXX."""
        return normalize_phone(value)
    

class SmsVerifySerializer(serializers.Serializer):
    """
    Сериализатор для проверки SMS-кода.

    Принимает номер и код. Номер нормализуется так же,
    как в PhoneRequestSerializer.
    """

    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=4, min_length=4)

    def validate_phone(self, value: str) -> str:
        """Нормализует номер к формату +7XXXXXXXXXX."""
        return normalize_phone(value)

    def validate_code(self, value: str) -> str:
        """Проверяет, что код состоит только из цифр."""
        if not value.isdigit():
            raise serializers.ValidationError('Код должен состоять из цифр')
        return value
