"""
Console SMS provider — выводит код в лог вместо отправки SMS.
"""

import logging

from apps.notifications.sms.base import SmsProvider

logger = logging.getLogger(__name__)


class ConsoleSmsProvider(SmsProvider):
    """
    Заглушка SMS-провайдера для разработки.

    Пишет SMS-код в лог на уровне INFO — разработчик видит код в консоли
    runserver и может им воспользоваться. В production должен заменяться
    реальным провайдером через factory/DI.

    В тестах уровень логгера повышается до WARNING (см. конфиг LOGGING
    в settings), поэтому INFO-вывод там не появляется.
    """

    def send(self, phone: str, code: str) -> bool:
        """
        Имитирует отправку SMS.
        """
        logger.info("=" * 60)
        logger.info("[SMS DEV] To: %s, Code: %s", phone, code)
        logger.info("=" * 60)
        logger.warning(
            "ConsoleSmsProvider used to send SMS to %s. This should never happen in production.",
            phone,
        )
        return True
