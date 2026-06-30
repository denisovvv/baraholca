"""
Фабрика SMS-провайдеров.

Выбирает нужную реализацию провайдера по настройке
SMS_PROVIDER в settings.py. Это позволяет менять провайдера
без изменений в коде, который запрашивает отправку SMS.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.notifications.sms.base import SmsProvider
from apps.notifications.sms.console import ConsoleSmsProvider

PROVIDERS = {
    "console": ConsoleSmsProvider,
    # 'sms_aero': SmsAeroProvider,  # будет добавлено, когда заказчик выберет
    # 'zvonok': ZvonokProvider,
}


PROVIDER_NOT_CONFIGURED_TEMPLATE = (
    "SMS_PROVIDER не задан в settings.py. Укажите одно из: {available}"
)
UNKNOWN_PROVIDER_TEMPLATE = "Неизвестный SMS-провайдер: {name}. Доступные: {available}"


def get_sms_provider() -> SmsProvider:
    """
    Возвращает экземпляр SMS-провайдера
    """
    provider_name = getattr(settings, "SMS_PROVIDER", None)

    if not provider_name:
        raise ImproperlyConfigured(
            PROVIDER_NOT_CONFIGURED_TEMPLATE.format(
                available=", ".join(PROVIDERS.keys()),
            )
        )

    provider_class = PROVIDERS.get(provider_name)
    if provider_class is None:
        raise ImproperlyConfigured(
            UNKNOWN_PROVIDER_TEMPLATE.format(
                name=provider_name,
                available=", ".join(PROVIDERS.keys()),
            )
        )

    return provider_class()
