"""
Иерархия доменных исключений приложения.

Применяется в сервисах и доменном слое; на границе DRF переводится
в HTTP-ответ через `apps.common.exception_handler.domain_exception_handler`
(см. README гайдлайнов: docs/guidelines/django/error_handling.md).

Принципы:
- Исключения - plain Python, без зависимостей от DRF/Django.
- Класс задаёт HTTP-категорию (401 / 404 / 409 / 422 / 429 / 500).
- `error_code` - стабильный машинно-читаемый код для клиента,
  передаётся при `raise` и характеризует конкретную причину.

Пример:
    raise NotFoundError("user_not_found", "Пользователь не найден")
    raise AuthenticationError("sms_code_invalid", "Неверный код")
    raise TooManyRequestsError("rate_limit_phone", "Слишком частые запросы")
"""


class AppError(Exception):
    """
    Корневое исключение приложения.

    Все доменные и сервисные ошибки наследуются от него.
    Сами по себе `AppError` без подкласса в коде не должны возникать -
    это абстрактный корень для `isinstance(exc, AppError)` в обработчике.
    """

    default_error_code = "app_error"
    default_message = "Внутренняя ошибка приложения"

    def __init__(self, error_code: str | None = None, message: str | None = None) -> None:
        self.error_code = error_code or self.default_error_code
        self.message = message or self.default_message
        super().__init__(self.message)


class DomainError(AppError):
    """
    Базовое доменное исключение - нарушение бизнес-правила.

    На транспортном уровне отображается в 4xx-ответы.
    В сервисах и доменном слое использовать наследников:
    `NotFoundError`, `ConflictError`, `ValidationError`,
    `AuthenticationError`, `TooManyRequestsError`.
    """

    default_error_code = "domain_error"
    default_message = "Нарушение бизнес-правила"


class NotFoundError(DomainError):
    """
    Запрашиваемая сущность не существует.

    Маппится на HTTP 404. Конкретику задавать через `error_code`:
    `user_not_found`, `product_not_found`, `order_not_found`.
    """

    default_error_code = "not_found"
    default_message = "Объект не найден"


class ConflictError(DomainError):
    """
    Конфликт состояния: дубликат, неверный переход состояния.

    Маппится на HTTP 409. Для rate-limit использовать `TooManyRequestsError`.
    Примеры `error_code`: `order_already_paid`, `phone_already_used`,
    `cart_already_checked_out`.
    """

    default_error_code = "conflict"
    default_message = "Конфликт состояния"


class ValidationError(DomainError):
    """
    Нарушение бизнес-валидации входных данных.

    Маппится на HTTP 422. Используется для бизнес-правил, которые
    нельзя поймать в сериализаторе (формат уже корректен,
    но семантика нарушена). Примеры `error_code`:
    `coordinates_out_of_range`, `discount_too_large`, `phone_format_invalid`.

    Не путать с `rest_framework.exceptions.ValidationError` -
    та сериализаторная, эта доменная.
    """

    default_error_code = "validation_error"
    default_message = "Ошибка валидации данных"


class AuthenticationError(DomainError):
    """
    Аутентификация не пройдена.

    Маппится на HTTP 401. Используется когда клиент не смог доказать,
    кто он (неверный код, истёкший токен и т.п.). Не путать с
    авторизацией (403): там клиент известен, но операция запрещена.

    Примеры `error_code`: `sms_code_invalid`, `sms_code_expired`,
    `sms_attempts_exhausted`, `token_invalid`.
    """

    default_error_code = "authentication_failed"
    default_message = "Аутентификация не пройдена"


class TooManyRequestsError(DomainError):
    """
    Превышен лимит частоты запросов.

    Маппится на HTTP 429. Используется для rate limiting на любом
    срезе: IP, пользователь, номер телефона, ключ API.

    Примеры `error_code`: `rate_limit_ip`, `rate_limit_phone`,
    `rate_limit_user`.
    """

    default_error_code = "too_many_requests"
    default_message = "Слишком много запросов"
