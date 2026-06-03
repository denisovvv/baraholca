"""
Скрипт массовой загрузки 11 реальных складов заказчика.

Запуск:
    cd ~/projects/baraxolka/backend
    source venv/bin/activate
    python manage.py shell < ../scripts/seed_warehouses.py
"""

from django.contrib.gis.geos import Point

from apps.catalog.models import Warehouse
from apps.sellers.models import Seller


# Данные складов: (название, ИНН продавца, адрес, широта, долгота)
WAREHOUSES = [
    # Радченко Ю.А. (ИНН 272292482306) — 4 склада
    ('Аксиома', '272292482306', 'с. Новая Усмань, ул. Ленина, 263Б', 51.6432, 39.4127),
    ('Европа', '272292482306', 'г. Старый Оскол, ул. Губкина, 1', 51.2967, 37.8392),
    ('Линия', '272292482306', 'г. Старый Оскол, ул. Лесной, 1', 51.3068, 37.8514),
    ('Славянский', '272292482306', 'г. Старый Оскол, ул. Ленина, 22', 51.2972, 37.8358),

    # Радченко Н.А. (ИНН 282201333000) — 3 склада
    ('ТЦ Маскарад', '282201333000', 'г. Старый Оскол, Молодежный пр-т, 10', 51.3132, 37.8689),
    ('Окей', '282201333000', 'г. Воронеж, ул. Шишкова, 72', 51.7257, 39.2178),
    ('Тенистый', '282201333000', 'г. Воронеж, ул. Тепличная, 4А', 51.7384, 39.2461),

    # Беседин Р.А. (ИНН 312830917909) — 4 склада
    ('Европа 53', '312830917909', 'г. Воронеж, Ленинский пр-т, 95Б', 51.6597, 39.2042),
    ('Линия (Губкин)', '312830917909', 'г. Губкин, ул. Севастопольская, 2А', 51.2837, 37.5614),
    ('Спутник', '312830917909', 'г. Губкин, ул. Преображенская, 7', 51.2895, 37.5732),
    ('Юго-западный', '312830917909', 'г. Воронеж, пр-т Патриотов, 3А', 51.6203, 39.1487),
]


def seed_warehouses():
    print('Старт загрузки складов...')
    print()

    # Загружаем продавцов в словарь по ИНН для быстрого доступа
    sellers_by_inn = {seller.inn: seller for seller in Seller.objects.all()}

    created_count = 0
    skipped_count = 0

    for name, inn, address, lat, lon in WAREHOUSES:
        # Проверяем что продавец существует
        seller = sellers_by_inn.get(inn)
        if not seller:
            print(f'⚠ Продавец с ИНН {inn} не найден, склад "{name}" пропущен')
            skipped_count += 1
            continue

        # Проверяем что такой склад ещё не создан (защита от повторного запуска)
        existing = Warehouse.objects.filter(
            name=name,
            seller=seller
        ).first()
        if existing:
            print(f'• "{name}" ({seller.short_name}) — уже существует, пропущено')
            skipped_count += 1
            continue

        # Создаём склад
        warehouse = Warehouse.objects.create(
            seller=seller,
            name=name,
            address=address,
            location=Point(lon, lat, srid=4326),  # PostGIS: Point(longitude, latitude)
            pickup_available=True,
            is_active=True,
        )

        print(f'✓ Создан: "{warehouse.name}" → {seller.short_name} → {address}')
        created_count += 1

    print()
    print(f'Готово. Создано: {created_count}, пропущено: {skipped_count}')


seed_warehouses()