"""
API views для пользователей и аутентификации.
"""

"""
API views для пользователей и аутентификации.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.sms.base import SmsProviderError
from apps.notifications.sms.factory import get_sms_provider
from apps.users.api.v1.serializers import (
    PhoneRequestSerializer,
    SmsVerifySerializer,
    UserSerializer,
)
from apps.users.api.v1.utils import (
    SMS_CODE_TTL,
    SMS_MAX_ATTEMPTS,
    SMS_RATE_IP_TTL,
    SMS_RATE_PHONE_TTL,
    delete_sms_code,
    generate_sms_code,
    get_attempts,
    get_client_ip,
    get_sms_code,
    increment_attempts,
    increment_rate_ip,
    increment_rate_phone,
    is_rate_limited_by_ip,
    is_rate_limited_by_phone,
    reset_attempts,
    save_sms_code,
)
from apps.users.models import User


@api_view(['GET'])
@permission_classes([AllowAny])
def ping(request):
    """
    Простой endpoint для проверки, что API работает.
    Не требует авторизации.
    """
    return Response({
        'status': 'ok',
        'message': 'API is running',
        'version': 'v1',
    })

class SmsRequestView(APIView):
    """
    Запрос SMS-кода для входа/регистрации.

    POST /api/v1/auth/sms/request/
    Body: {"phone": "+79991234567"}

    Публичный endpoint (без авторизации).

    Порядок проверок:
    1. Валидация и нормализация номера
    2. Rate limit по IP (5/час)
    3. Rate limit по номеру (1/мин)
    4. Генерация и сохранение кода, отправка SMS

    Ответы:
    - 200: {"status": "sent", "expires_in": 300}
    - 400: невалидный номер
    - 429: превышен rate limit
    - 503: ошибка отправки SMS
    """

    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Валидация номера
        serializer = PhoneRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        client_ip = get_client_ip(request)

        # 2. Rate limit по IP
        if is_rate_limited_by_ip(client_ip):
            return Response(
                {
                    'detail': 'Слишком много запросов с вашего адреса. '
                              'Попробуйте позже.',
                    'retry_after': SMS_RATE_IP_TTL,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # 3. Rate limit по номеру
        if is_rate_limited_by_phone(phone):
            return Response(
                {
                    'detail': 'Код уже был отправлен. '
                              'Повторный запрос возможен через минуту.',
                    'retry_after': SMS_RATE_PHONE_TTL,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # 4. Генерация и сохранение кода
        code = generate_sms_code()
        save_sms_code(phone, code)

        # 5. Отправка SMS через провайдера
        sms_provider = get_sms_provider()
        try:
            sent = sms_provider.send(phone, code)
        except SmsProviderError:
            # Провайдер недоступен — не штрафуем пользователя rate limit'ом
            return Response(
                {'detail': 'Не удалось отправить SMS. Попробуйте позже.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not sent:
            return Response(
                {'detail': 'Не удалось отправить SMS. Попробуйте позже.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 6. Инкремент счётчиков rate limit (только после успешной отправки)
        increment_rate_ip(client_ip)
        increment_rate_phone(phone)

        # 7. Успех
        return Response(
            {
                'status': 'sent',
                'expires_in': SMS_CODE_TTL,
            },
            status=status.HTTP_200_OK,
        )
    
class SmsVerifyView(APIView):
    """
    Проверка SMS-кода и выдача JWT-токенов.

    POST /api/v1/auth/sms/verify/
    Body: {"phone": "+79991112233", "code": "1234"}

    Публичный endpoint.

    При верном коде:
    - находит существующего пользователя или создаёт нового
    - помечает phone_verified = True
    - выдаёт access и refresh токены

    Защита от перебора: не более SMS_MAX_ATTEMPTS попыток на код.

    Ответы:
    - 200: токены + профиль пользователя
    - 400: невалидные данные
    - 401: неверный код (с остатком попыток) или код истёк
    """

    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Валидация входных данных
        serializer = SmsVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        code = serializer.validated_data['code']

        # 2. Достаём код из Redis
        stored_code = get_sms_code(phone)
        if stored_code is None:
            # Кода нет: не запрашивали, истёк, или уже исчерпали попытки
            return Response(
                {'detail': 'Код недействителен. Запросите новый.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 3. Проверяем количество попыток
        attempts = get_attempts(phone)
        if attempts >= SMS_MAX_ATTEMPTS:
            # Исчерпаны попытки — инвалидируем код
            delete_sms_code(phone)
            reset_attempts(phone)
            return Response(
                {'detail': 'Слишком много попыток. Запросите новый код.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 4. Сравниваем код
        if code != stored_code:
            new_attempts = increment_attempts(phone)
            remaining = SMS_MAX_ATTEMPTS - new_attempts

            if remaining <= 0:
                # Это была последняя попытка — инвалидируем код
                delete_sms_code(phone)
                reset_attempts(phone)
                return Response(
                    {'detail': 'Слишком много попыток. Запросите новый код.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            return Response(
                {'detail': f'Неверный код. Осталось попыток: {remaining}'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 5. Код верный — находим или создаём пользователя
        user, is_new_user = User.objects.get_or_create(
            phone=phone,
            defaults={'phone_verified': True},
        )

        # Если пользователь уже был, но номер не был подтверждён — подтверждаем
        if not user.phone_verified:
            user.phone_verified = True
            user.save(update_fields=['phone_verified'])

        # 6. Чистим Redis: код и попытки больше не нужны
        delete_sms_code(phone)
        reset_attempts(phone)

        # 7. Генерируем JWT-токены
        refresh = RefreshToken.for_user(user)

        # 8. Возвращаем токены и профиль
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
                'is_new_user': is_new_user,
            },
            status=status.HTTP_200_OK,
        )