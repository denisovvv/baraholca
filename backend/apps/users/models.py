from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """
    Менеджер для создания пользователей по номеру телефона.
    """

    def create_user(self, phone, password=None, **extra_fields):
        """
        Создаёт обычного пользователя (покупателя) по номеру телефона.
        Пароль обычно не указывается — покупатели входят по коду подтверждения.
        """
        if not phone:
            raise ValueError('Не указан номер телефона')

        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        """
        Создаёт суперпользователя для администрирования.
        Обязательно с паролем, обязательно с правами админки.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True')
        if not password:
            raise ValueError('Суперпользователь должен иметь пароль')

        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Кастомная модель пользователя.
    Авторизация по номеру телефона.
    """

    phone = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Номер телефона',
        help_text='В международном формате, например: +79991234567'
    )
    first_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Имя'
    )
    last_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Фамилия'
    )
    email = models.EmailField(
        blank=True,
        verbose_name='Email'
    )

    # Социальная авторизация
    phone_verified = models.BooleanField(
        default=False,
        verbose_name='Телефон подтверждён',
        help_text='Подтверждён ли телефон через flash call или SMS'
    )
    vk_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name='VK ID',
        help_text='ID пользователя в VK (для входа через VK ID)'
    )
    apple_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Apple ID',
        help_text='ID пользователя в Apple (sub-токен из Apple Sign In)'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name='Доступ в админку',
        help_text='Если включено — пользователь может входить в админ-панель'
    )

    date_joined = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата регистрации'
    )

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-date_joined']

    def __str__(self):
        if self.first_name or self.last_name:
            return f'{self.phone} ({self.first_name} {self.last_name})'.strip()
        return self.phone

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name or self.phone