"""
Console SMS provider — выводит код в консоль вместо отправки SMS.
"""

import logging

from apps.notifications.sms.base import SmsProvider


logger = logging.getLogger(__name__)


class ConsoleSmsProvider(SmsProvider):
    """
    Заглушка SMS-провайдера для разработки.
    """

    def send(self, phone: str, code: str) -> bool:
        """
        Имитирует отправку SMS
        """
        message = f'[SMS DEV] To: {phone}, Code: {code}'

        # В консоль терминала где работает runserver
        print('=' * 60)
        print(message)
        print('=' * 60)

      
        logger.warning(
            'ConsoleSmsProvider used to send SMS to %s. '
            'This should never happen in production.',
            phone,
        )

        return True