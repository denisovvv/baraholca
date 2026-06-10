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

from apps.notifications.sms.base import SmsProviderError
from apps.notifications.sms.factory import get_sms_provider
from apps.users.api.v1.serializers import PhoneRequestSerializer
from apps.users.api.v1.utils import (
    SMS_CODE_TTL,
    SMS_RATE_IP_TTL,
    SMS_RATE_PHONE_TTL,
    generate_sms_code,
    get_client_ip,
    increment_rate_ip,
    increment_rate_phone,
    is_rate_limited_by_ip,
    is_rate_limited_by_phone,
    save_sms_code,
)


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