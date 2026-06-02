from django.db import models
from django.utils.text import slugify


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
    