"""
API views для пользователей и аутентификации.
"""

from rest_framework import status
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


class SmsRequestView(APIView):
    """
    Запрос SMS-кода для входа/регистрации.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PhoneRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        client_ip = get_client_ip(request)
        if is_rate_limited_by_ip(client_ip):
            return Response(
                {
                    "detail": "Слишком много запросов с вашего адреса. Попробуйте позже.",
                    "retry_after": SMS_RATE_IP_TTL,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if is_rate_limited_by_phone(phone):
            return Response(
                {
                    "detail": "Код уже был отправлен. Повторный запрос возможен через минуту.",
                    "retry_after": SMS_RATE_PHONE_TTL,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        code = generate_sms_code()
        save_sms_code(phone, code)

        sms_provider = get_sms_provider()
        try:
            sent = sms_provider.send(phone, code)
        except SmsProviderError:
            # Провайдер недоступен — не штрафуем пользователя rate limit'ом
            return Response(
                {"detail": "Не удалось отправить SMS. Попробуйте позже."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not sent:
            return Response(
                {"detail": "Не удалось отправить SMS. Попробуйте позже."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Инкремент только после успешной отправки
        increment_rate_ip(client_ip)
        increment_rate_phone(phone)

        return Response(
            {
                "status": "sent",
                "expires_in": SMS_CODE_TTL,
            },
            status=status.HTTP_200_OK,
        )


class SmsVerifyView(APIView):
    """
    Проверка SMS-кода и выдача JWT-токенов.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SmsVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        stored_code = get_sms_code(phone)
        if stored_code is None:
            # Кода нет: не запрашивали, истёк, или уже исчерпали попытки
            return Response(
                {"detail": "Код недействителен. Запросите новый."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        attempts = get_attempts(phone)
        if attempts >= SMS_MAX_ATTEMPTS:
            # Исчерпаны попытки — инвалидируем код
            delete_sms_code(phone)
            reset_attempts(phone)
            return Response(
                {"detail": "Слишком много попыток. Запросите новый код."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if code != stored_code:
            new_attempts = increment_attempts(phone)
            remaining = SMS_MAX_ATTEMPTS - new_attempts

            if remaining <= 0:
                # Это была последняя попытка — инвалидируем код
                delete_sms_code(phone)
                reset_attempts(phone)
                return Response(
                    {"detail": "Слишком много попыток. Запросите новый код."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            return Response(
                {"detail": f"Неверный код. Осталось попыток: {remaining}"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user, is_new_user = User.objects.get_or_create(
            phone=phone,
            defaults={"phone_verified": True},
        )

        # Если пользователь уже был, но номер не был подтверждён — подтверждаем
        if not user.phone_verified:
            user.phone_verified = True
            user.save(update_fields=["phone_verified"])

        delete_sms_code(phone)
        reset_attempts(phone)

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
                "is_new_user": is_new_user,
            },
            status=status.HTTP_200_OK,
        )
