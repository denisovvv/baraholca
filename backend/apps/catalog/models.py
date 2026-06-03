from django.contrib.gis.db import models as gis_models
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError


class Category(models.Model):
    """
    Категория товаров. Поддерживает вложенность (категория → подкатегория).
    Максимальная глубина — 3 уровня.

    Категории создаются и редактируются в админке приложения.
    Из 1С не синхронизируются.
    """

    name = models.CharField(
        max_length=100,
        verbose_name='Название'
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        verbose_name='URL-идентификатор',
        help_text='Заполнится автоматически, если оставить пустым'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        verbose_name='Изображение'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Порядок сортировки',
        help_text='Чем меньше число, тем выше в списке'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна',
        help_text='Если выключено — категория и её товары не отображаются в каталоге'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создана'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлена'
    )

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']

    def __str__(self):
        return self.get_full_path()

    def save(self, *args, **kwargs):
        # Автогенерация slug, если не заполнен
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def get_full_path(self):
        """
        Возвращает полный путь категории через все родительские.
        Например: 'Одежда / Мужская / Куртки'
        """
        if self.parent:
            return f'{self.parent.get_full_path()} / {self.name}'
        return self.name

    def get_level(self):
        """
        Возвращает уровень вложенности категории (0 для корневых).
        """
        if self.parent:
            return self.parent.get_level() + 1
        return 0
    
    def clean(self):
        """
        Валидация на уровне модели:
        - Запрещаем глубину вложенности больше 3 уровней
        - Запрещаем категории быть собственным родителем (циклы)
        """
        # Проверка циклов — категория не может быть родителем самой себе
        if self.parent and self.parent == self:
            raise ValidationError({
                'parent': 'Категория не может быть родителем самой себе'
            })

        # Проверка глубины — максимум 3 уровня (0, 1, 2)
        if self.parent:
            # get_level() считает от 0 — если у родителя level=2, то у нас будет level=3, что уже слишком
            if self.parent.get_level() >= 2:
                raise ValidationError({
                    'parent': 'Превышена максимальная глубина вложенности (3 уровня)'
                })

        # Проверка цикла через родителей — не допускаем, чтобы категория была своим прапредком
        if self.parent and self.pk:
            parent = self.parent
            while parent:
                if parent.pk == self.pk:
                    raise ValidationError({
                        'parent': 'Обнаружен цикл — категория не может быть потомком самой себя'
                    })
                parent = parent.parent
    
class Warehouse(models.Model):
    """
    Склад / точка продавца.

    UUID склада приходит из 1С. Координаты центра и полигон зоны доставки
    ведутся в админке приложения.
    """

    uuid_1c = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        verbose_name='UUID в 1С',
        help_text='Идентификатор склада в системе 1С'
    )
    seller = models.ForeignKey(
        'sellers.Seller',
        on_delete=models.CASCADE,
        related_name='warehouses',
        verbose_name='Продавец'
    )
    name = models.CharField(
        max_length=150,
        verbose_name='Название',
        help_text='Например: «Склад на Ленина, 5»'
    )
    address = models.CharField(
        max_length=500,
        verbose_name='Адрес'
    )

    # Геоданные — центр склада (для отображения на карте)
    location = gis_models.PointField(
        verbose_name='Координаты центра',
        help_text='Точка на карте, где расположен склад',
        srid=4326
    )

    # Геоданные — зона доставки (полигон)
    delivery_area = gis_models.PolygonField(
        null=True,
        blank=True,
        verbose_name='Зона доставки',
        help_text='Полигон территории, на которую этот склад доставляет курьером',
        srid=4326
    )

    pickup_available = models.BooleanField(
        default=True,
        verbose_name='Доступен самовывоз',
        help_text='Может ли покупатель забрать заказ с этого склада'
    )

    working_hours = models.JSONField(
        blank=True,
        null=True,
        verbose_name='Часы работы',
        help_text='Часы работы по дням недели в формате JSON'
    )

    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Контактный телефон',
        help_text='Телефон склада для покупателей при самовывозе'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создан'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлён'
    )

    class Meta:
        verbose_name = 'Склад'
        verbose_name_plural = 'Склады'
        ordering = ['seller__name', 'name']

    def __str__(self):
        return f'{self.name} ({self.seller.short_name or self.seller.name})'
    

    