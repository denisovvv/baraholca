"""
Абстрактный интерфейс SMS-провайдера.
"""

from abc import ABC, abstractmethod


class SmsProvider(ABC):
    """
    Абстрактный SMS-провайдер.
    """

    @abstractmethod
    def send(self, phone: str, code: str) -> bool:
        """
        Отправить SMS с кодом подтверждения на указанный номер.

        Args:
            phone: Номер телефона в формате '+7XXXXXXXXXX'
            code: Код подтверждения, обычно 4 цифры

        Returns:
            True если отправлено успешно, False в случае ошибки.

        Конкретные реализации должны логировать факт отправки,
        но НЕ должны логировать сам код — это чувствительные данные.
        """
        raise NotImplementedError


class SmsProviderError(Exception):
    """
    Базовое исключение для ошибок SMS-провайдера.

    Конкретные реализации могут выбрасывать своих наследников
    (например, SmsAeroAuthError, SmsAeroQuotaError), а вызывающий
    код может ловить либо конкретное, либо базовое.
    """
    pass
