from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, verbose_name="Email")
    avatar = models.ImageField(upload_to="avatars", verbose_name="Аватар", blank=True)
    phone_number = models.CharField(
        max_length=20,
        verbose_name="Номер телефона",
        null=True,
        unique=True,
        blank=True,
    )
    country = models.CharField(
        verbose_name="Страна", null=True, blank=True, max_length=100
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_banned = models.BooleanField(default=False, verbose_name="Бан")
    is_staff = models.BooleanField(default=False, verbose_name="Сотрудник")
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        permissions = [
            ("can_view_user_list", "Can view user list"),
            ("can_ban", "Can ban user"),
        ]

    def __str__(self):
        email_status = "Email не подтвержден"
        banned = "Активен"
        if self.is_active:
            email_status = "Email подтвержден"
        if self.is_banned:
            banned = "Заблокирован"

        return f"{self.username} - {self.email} | {email_status} | {banned}"
