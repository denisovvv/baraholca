"""
Data-миграция: заполнение order_prefix для трёх существующих Seller.

Требуется перед добавлением UNIQUE constraint (в следующей миграции),
иначе UNIQUE на трёх пустых строках упадёт с IntegrityError.

Префиксы согласованы с владельцем проекта:
  id=1 (Радченко Ю.А.) → RYA
  id=4 (Радченко Н.А.) → RNA
  id=5 (Беседин Р.А.)  → BRA

reverse_populate откатывает изменение — обнуляет префиксы обратно.
Это позволяет корректно "отматывать" миграции назад при отладке.
"""

from django.db import migrations

# Соответствие id продавца -> префикс. Задано вручную с согласованием
# с владельцем проекта. При добавлении новых продавцов префикс задаётся
# через админку (см. SellerAdmin в apps/sellers/admin.py).
SELLER_PREFIXES = {
    1: "RYA",
    4: "RNA",
    5: "BRA",
}


def populate_order_prefix(apps, schema_editor):
    """
    Проставить префикс каждому Seller согласно SELLER_PREFIXES.

    Использует historical model через apps.get_model — снимок структуры
    Seller на момент этой миграции. Не импортируем модель напрямую, потому
    что в будущем модель может измениться, а старая миграция должна работать
    корректно относительно своего состояния схемы.
    """
    Seller = apps.get_model("sellers", "Seller")
    for seller_id, prefix in SELLER_PREFIXES.items():
        Seller.objects.filter(pk=seller_id).update(order_prefix=prefix)


def reverse_populate(apps, schema_editor):
    """
    Откатить проставление префиксов — вернуть пустую строку.

    Нужна для migrate zero или migrate назад: без reverse-функции
    Django не сможет откатить эту миграцию.
    """
    Seller = apps.get_model("sellers", "Seller")
    for seller_id in SELLER_PREFIXES:
        Seller.objects.filter(pk=seller_id).update(order_prefix="")


class Migration(migrations.Migration):
    dependencies = [
        ("sellers", "0003_seller_order_prefix"),
    ]

    operations = [
        migrations.RunPython(populate_order_prefix, reverse_populate),
    ]
