"""
Сериализаторы для API пользователей.

UserSerializer — представление профиля пользователя для мобильного приложения.
Скрывает все внутренние и серверные поля.
"""

from rest_framework import serializers

from apps.users.models import User


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