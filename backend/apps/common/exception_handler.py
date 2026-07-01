"""
Кастомный обработчик исключений DRF.

Подключается через REST_FRAMEWORK["EXCEPTION_HANDLER"] в settings.
Маппит доменные исключения (apps.common.exceptions) и стандартные DRF
исключения в единый контракт ответа:

    {
        "error": {
            "code": "<machine_readable>",
            "message": "<human_readable>"
        }
    }

См. docs/guidelines/django/error_handling.md.
"""

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.common.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    TooManyRequestsError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# Таблица маппинга доменных исключений в HTTP-статусы.
# Порядок строк важен: специфичные подклассы перед предками,
# чтобы первое isinstance-совпадение давало правильный статус.
_DOMAIN_ERROR_STATUSES: list[tuple[type[AppError], int]] = [
    (AuthenticationError, status.HTTP_401_UNAUTHORIZED),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (ValidationError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (TooManyRequestsError, status.HTTP_429_TOO_MANY_REQUESTS),
    (DomainError, status.HTTP_400_BAD_REQUEST),
]


def _error_response(code: str, message: str, http_status: int) -> Response:
    """
    Сформировать ответ в едином формате `{"error": {"code", "message"}}`.
    """
    return Response(
        {"error": {"code": code, "message": message}},
        status=http_status,
    )


def domain_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response | None:
    """
    Обработчик исключений уровня сервиса.

    1. Если это AppError - доменное, маппим в наш формат через _handle_app_error.
    2. Иначе - даём отработать DRF (ValidationError, PermissionDenied, ...),
       его ответ переоборачиваем в наш формат.
    3. Совсем необработанные - 500, traceback в лог.
    """
    if isinstance(exc, AppError):
        return _handle_app_error(exc)

    response = drf_exception_handler(exc, context)
    if response is not None:
        return _rewrap_drf_response(response, exc)

    logger.exception(
        "Unhandled exception in view",
        extra={"view": context.get("view"), "request": context.get("request")},
    )
    return _error_response(
        "internal_error",
        "Внутренняя ошибка сервиса. Попробуйте позже.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _handle_app_error(exc: AppError) -> Response:
    """
    Маппинг доменного исключения в HTTP-ответ.

    Итерирует _DOMAIN_ERROR_STATUSES в декларативном порядке и возвращает
    ответ для первого подходящего класса. Если ни один не совпал -
    значит, это AppError без подкласса (бага кода): логируем и отдаём 500.
    """
    for exc_class, http_status in _DOMAIN_ERROR_STATUSES:
        if isinstance(exc, exc_class):
            return _error_response(exc.error_code, exc.message, http_status)

    logger.exception("AppError leaked to handler without domain subclass")
    return _error_response(exc.error_code, exc.message, status.HTTP_500_INTERNAL_SERVER_ERROR)


def _rewrap_drf_response(response: Response, exc: Exception) -> Response:
    """
    Переоборачивает стандартный ответ DRF в наш формат {"error": {"code", "message"}}.

    Тип DRF-исключения определяет `code`, текст исключения - `message`.

    Для DRF ValidationError переопределяем статус с 400 на 422:
    единый contract требует что все "невалидное тело запроса" - это 422,
    независимо от источника (наш доменный ValidationError или DRF-сериализатор).
    Клиенту не нужно различать эти случаи - для него это одна семантическая
    категория "твоё тело не прошло проверку".
    """
    code = _drf_exception_code(exc)
    message = _drf_extract_message(response.data)
    http_status = response.status_code
    if type(exc).__name__ == "ValidationError":
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    return _error_response(code, message, http_status)


def _drf_exception_code(exc: Exception) -> str:
    """
    Маппинг стандартных DRF-исключений на стабильные `error_code`.

    Для незнакомых классов - имя класса в snake_case.
    """
    mapping = {
        "ValidationError": "validation_error",
        "NotAuthenticated": "not_authenticated",
        "AuthenticationFailed": "authentication_failed",
        "PermissionDenied": "permission_denied",
        "NotFound": "not_found",
        "Http404": "not_found",
        "MethodNotAllowed": "method_not_allowed",
        "NotAcceptable": "not_acceptable",
        "UnsupportedMediaType": "unsupported_media_type",
        "Throttled": "throttled",
    }
    name = type(exc).__name__
    return mapping.get(name, "request_error")


def _drf_extract_message(
    data: Any,  # noqa: ANN401  # response.data DRF может быть str | list | dict вложенно
) -> str:
    """
    Превращает payload DRF-исключения (dict / list / str) в одну строку-сообщение.

    DRF ValidationError возвращает либо `{"field": ["msg1", "msg2"]}`,
    либо `["msg1"]`, либо `"msg1"`. Для единого контракта склеиваем в строку.
    """
    if isinstance(data, str):
        return data

    if isinstance(data, list):
        return "; ".join(str(item) for item in data)

    if isinstance(data, dict):
        # Если ровно одно поле "detail" - типичный кейс DRF, отдаём его текст.
        if set(data.keys()) == {"detail"}:
            return str(data["detail"])
        # Иначе склеиваем поля: "field1: msg; field2: msg".
        parts: list[str] = []
        for key, value in data.items():
            if isinstance(value, list):
                value_str = "; ".join(str(item) for item in value)
            else:
                value_str = str(value)
            parts.append(f"{key}: {value_str}")
        return " | ".join(parts)

    return str(data)
