"""
Кастомные формы и виджеты для приложения catalog.
"""

import json

from django import forms


DAYS_OF_WEEK = [
    ('monday', 'Понедельник'),
    ('tuesday', 'Вторник'),
    ('wednesday', 'Среда'),
    ('thursday', 'Четверг'),
    ('friday', 'Пятница'),
    ('saturday', 'Суббота'),
    ('sunday', 'Воскресенье'),
]


class WorkingHoursWidget(forms.Widget):
    """
    Виджет для редактирования часов работы по дням недели.
    Вместо JSON показывает удобную таблицу с галочками и полями времени.

    Хранит данные в БД как JSON формата:
    {
        "monday": {"open": "09:00", "close": "21:00"},
        "sunday": null
    }
    """

    template_name = 'admin/widgets/working_hours.html'

    def __init__(self, attrs=None):
        super().__init__(attrs)

    def value_from_datadict(self, data, files, name):
        """
        Вызывается при сохранении формы — собирает данные обратно в JSON.
        """
        result = {}
        for day_key, day_label in DAYS_OF_WEEK:
            is_open = data.get(f'{name}_{day_key}_open_flag') == 'on'
            if is_open:
                open_time = data.get(f'{name}_{day_key}_open_time', '').strip()
                close_time = data.get(f'{name}_{day_key}_close_time', '').strip()
                if open_time and close_time:
                    result[day_key] = {'open': open_time, 'close': close_time}
                else:
                    result[day_key] = None
            else:
                result[day_key] = None
        return json.dumps(result, ensure_ascii=False)

    def get_context(self, name, value, attrs):
        """
        Готовит данные для отображения в шаблоне.
        """
        context = super().get_context(name, value, attrs)

        # Парсим существующие данные
        parsed = {}
        if value:
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except (ValueError, TypeError):
                    parsed = {}
            elif isinstance(value, dict):
                parsed = value

        # Готовим строки для шаблона
        days = []
        for day_key, day_label in DAYS_OF_WEEK:
            day_data = parsed.get(day_key)
            is_open = day_data is not None and isinstance(day_data, dict)
            days.append({
                'key': day_key,
                'label': day_label,
                'is_open': is_open,
                'open_time': day_data.get('open', '09:00') if is_open else '09:00',
                'close_time': day_data.get('close', '21:00') if is_open else '21:00',
            })

        context['widget']['days'] = days
        context['widget']['field_name'] = name
        return context


class WorkingHoursFormField(forms.CharField):
    """
    Поле формы для часов работы.
    Использует WorkingHoursWidget, хранит значение как JSON-строку.
    """
    widget = WorkingHoursWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        """
        Возвращает Python-объект из строки JSON.
        Django при сохранении в JSONField сам поймёт что это dict.
        """
        if not value:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None