"""
Console SMS provider — выводит код в консоль вместо отправки SMS.

Используется только в разработке и тестах.
В production должен использоваться реальный провайдер
(SmsAero, Zvonok, etc).
"""

import logging

from apps.notifications.sms.base import SmsProvider


logger = logging.getLogger(__name__)


class ConsoleSmsProvider(SmsProvider):
    """
    Заглушка SMS-провайдера для разработки.

    Вместо отправки SMS выводит сообщение в консоль и в логи.
    Код виден разработчику в терминале runserver, поэтому
    в production использовать НЕЛЬЗЯ.
    """

    def send(self, phone: str, code: str) -> bool:
        """
        Имитирует отправку SMS, выводя данные в консоль.
        В консоли видны и телефон, и код — это только для dev-окружения.
        """
        message = f'[SMS DEV] To: {phone}, Code: {code}'

        # В консоль терминала где работает runserver
        print('=' * 60)
        print(message)
        print('=' * 60)

        # В стандартный логгер Django (попадёт в лог-файлы прода,
        # если ConsoleSmsProvider ошибочно окажется на проде —
        # будет видно в мониторинге)
        logger.warning(
            'ConsoleSmsProvider used to send SMS to %s. '
            'This should never happen in production.',
            phone,
        )

        return True