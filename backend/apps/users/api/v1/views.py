"""
API views для пользователей и аутентификации.
"""

from typing import ClassVar

from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.exceptions import AuthenticationError, TooManyRequestsError, ValidationError
from apps.notifications.sms.base import SmsProviderError
from apps.notifications.sms.factory import get_sms_provider
from apps.users.api.v1.serializers import (
    PhoneRequestSerializer,
    SmsVerifySerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.users.api.v1.utils import (
    SMS_CODE_TTL,
    SMS_MAX_ATTEMPTS,
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

    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]

    def post(self, request: Request) -> Response:
        serializer = PhoneRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        client_ip = get_client_ip(request)
        if is_rate_limited_by_ip(client_ip):
            raise TooManyRequestsError(
                "rate_limit_ip",
                "Слишком много запросов с вашего адреса. Попробуйте позже.",
            )

        if is_rate_limited_by_phone(phone):
            raise TooManyRequestsError(
                "rate_limit_phone",
                "Код уже был отправлен. Повторный запрос возможен через минуту.",
            )

        code = generate_sms_code()
        save_sms_code(phone, code)

        sms_provider = get_sms_provider()
        try:
            sent = sms_provider.send(phone, code)
        except SmsProviderError:
            # Провайдер недоступен — не штрафуем пользователя rate limit'ом.
            # TODO: завести ServiceUnavailableError и перейти на raise.
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

    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]  # type: ignore[misc]

    def post(self, request: Request) -> Response:
        serializer = SmsVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        stored_code = get_sms_code(phone)
        if stored_code is None:
            # Кода нет: не запрашивали, истёк, или уже исчерпали попытки
            raise AuthenticationError(
                "sms_code_expired",
                "Код недействителен. Запросите новый.",
            )

        attempts = get_attempts(phone)
        if attempts >= SMS_MAX_ATTEMPTS:
            # Исчерпаны попытки — инвалидируем код
            delete_sms_code(phone)
            reset_attempts(phone)
            raise AuthenticationError(
                "sms_attempts_exhausted",
                "Слишком много попыток. Запросите новый код.",
            )

        if code != stored_code:
            new_attempts = increment_attempts(phone)
            remaining = SMS_MAX_ATTEMPTS - new_attempts

            if remaining <= 0:
                # Это была последняя попытка — инвалидируем код
                delete_sms_code(phone)
                reset_attempts(phone)
                raise AuthenticationError(
                    "sms_attempts_exhausted",
                    "Слишком много попыток. Запросите новый код.",
                )

            raise AuthenticationError(
                "sms_code_invalid",
                f"Неверный код. Осталось попыток: {remaining}",
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


class UserMeView(APIView):
    """
    Профиль текущего пользователя.

    GET — вернуть свой профиль.
    PATCH — частично обновить свой профиль (first_name, last_name).

    Endpoint работает только с request.user — доступа к чужим профилям
    нет по дизайну (нет id в URL). Требует аутентификации.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]  # type: ignore[misc]

    def get(self, request: Request) -> Response:
        """
        Вернуть профиль текущего пользователя.
        """
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request) -> Response:
        """
        Частично обновить профиль текущего пользователя.

        Пустое тело запроса считается ошибкой клиента (обычно баг формы,
        не собравшей изменённые поля) — отвечаем 422 nothing_to_update,
        чтобы разработчик Flutter быстро увидел проблему.
        """
        if not request.data:
            raise ValidationError(
                "nothing_to_update",
                "Не переданы поля для обновления.",
            )

        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Отдаём полный профиль после обновления (не только изменённые поля).
        # Клиенту удобнее иметь актуальное состояние целиком одним ответом.
        read_serializer = UserSerializer(request.user)
        return Response(read_serializer.data, status=status.HTTP_200_OK)
