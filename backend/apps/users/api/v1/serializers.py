"""
Сериализаторы для API пользователей.

UserSerializer — представление профиля пользователя для мобильного приложения.
Скрывает все внутренние и серверные поля.
"""

from rest_framework import serializers

from apps.users.models import User

import re

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
        """
        Нормализует и проверяет номер телефона.

        Принимает форматы:
            +79991234567
            89991234567
            7 999 123-45-67
            +7 (999) 123-45-67

        Возвращает строго +7XXXXXXXXXX или кидает ValidationError.
        """
        # Убираем всё кроме цифр
        digits = re.sub(r'\D', '', value)

        # Приводим к формату 7XXXXXXXXXX
        if digits.startswith('8') and len(digits) == 11:
            # 89991234567 → 79991234567
            digits = '7' + digits[1:]
        elif digits.startswith('7') and len(digits) == 11:
            # уже 79991234567 — ок
            pass
        else:
            raise serializers.ValidationError(
                'Введите корректный номер телефона в формате +7XXXXXXXXXX'
            )

        # Финальная проверка: ровно 11 цифр, начинается с 7
        if len(digits) != 11 or not digits.startswith('7'):
            raise serializers.ValidationError(
                'Введите корректный номер телефона в формате +7XXXXXXXXXX'
            )

        # Возвращаем в формате +7XXXXXXXXXX
        return '+' + digits