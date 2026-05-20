import os
from pathlib import Path
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from dotenv import load_dotenv
import smtplib
from http.client import HTTPException

from django.core.mail import send_mail
from django.db import models
from users.models import CustomUser

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=BASE_DIR / ".env")


class Recipient(models.Model):
    email = models.EmailField(verbose_name="Email", unique=True)
    title = models.CharField(verbose_name="Название", null=True, blank=True, max_length=255)
    comment = models.TextField(verbose_name="Комментарий", null=True, blank=True)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)

    def __str__(self):
        # Получаем заголовки сообщений, связанных с этим получателем
        messages = MailingList.objects.filter(recipients=self).values_list('message__title', flat=True)
        total = messages.count()

        # Формируем отображение списка рассылок
        if total == 0:
            messages_display = "нет"
        else:
            first_two = list(messages[:2])  # берём первые два заголовка
            rest = total - 2
            if rest > 0:
                messages_display = ", ".join(first_two) + f" (+{rest})"
            else:
                messages_display = ", ".join(first_two)

        # Выбираем индикатор: зелёный квадрат, если есть рассылки, иначе чёрный
        label = "⬛" if total == 0 else "🟩"

        return f"{label} {self.title}({self.email}) Связанные рассылки: {messages_display}"

    class Meta:
        verbose_name = "Получатель"
        verbose_name_plural = "Получатели"
        ordering = ["email"]
        permissions = [
            ("can_view_recipient", "Can view recipient"),
        ]


class Message(models.Model):
    title = models.CharField(verbose_name="Тема письма", max_length=255)
    body = models.TextField(verbose_name="Текст письма")
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ["title"]
        permissions = [
            ("can_view_message", "Can view message"),
        ]


class MailingList(models.Model):
    STATUS_CHOICES = [
        ("created", "Создана"),
        ("started", "Запущена"),
        ("completed", "Завершена"),
    ]

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"
        permissions = [
            ("can_view_mailing_list", "Can view mailing list"),
            ("can_turn_off", "Can turn off mailing list"),
        ]

    date_first_sent = models.DateTimeField(
        verbose_name="Дата первой отправки", auto_now_add=True
    )
    date_last_sent = models.DateTimeField(
        verbose_name="Дата последней отправки", auto_now=True
    )
    status = models.CharField(
        verbose_name="Статус", choices=STATUS_CHOICES, max_length=10, default="created"
    )
    message = models.ForeignKey(
        Message, verbose_name="Сообщение", on_delete=models.CASCADE
    )
    recipients = models.ManyToManyField(Recipient, verbose_name="Получатели")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"id:{self.pk} | {self.message} | {self.recipients}"

    def send(self):
        if not self.is_active:
            raise HTTPException("Вы не можете запустить рассылку т.к. она отключена менеджером")
        self.status = "started"
        self.save()

        subject = self.message.title
        message = self.message.body
        phone = self.owner.phone_number
        email = self.owner.email
        from_email = f'"Компьютерный салон FROMOZA" <{os.getenv("EMAIL_HOST_USER")}>'
        recipient_emails = [r.email for r in self.recipients.all()]
        html_content = render_to_string('mail_template.html', context={
            'title': subject,
            'message_body': message,
            'phone': phone,
            'contact_email': email,
            'address': 'г. Северодвинск, ул. Ломоносова 102а, компьютерный салон Formoza',
            'logo_url': 'https://formoza29.net/images/logo5.jpg',
        })

        success_count = 0
        for recipient in recipient_emails:
            try:
                msg = EmailMultiAlternatives(
                    subject,
                    message,
                    from_email,
                    [recipient],
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send()
                success_count += 1
                SendAttempt.objects.create(
                    mailing_list=self,
                    status="Успешно",
                    response="Письмо успешно отправлено",
                    owner=self.owner,
                )
            except smtplib.SMTPException as e:
                SendAttempt.objects.create(
                    mailing_list=self,
                    status="Не успешно",
                    response=f"SMTP ошибка: {str(e)}",
                    owner=self.owner,
                )
            except Exception as e:
                SendAttempt.objects.create(
                    mailing_list=self,
                    status="Не успешно",
                    response=f"Неизвестная ошибка: {str(e)}",
                    owner=self.owner,
                )

        self.status = "completed"
        self.save()
        return success_count


class SendAttempt(models.Model):
    date = models.DateTimeField(verbose_name="Дата", auto_now_add=True)
    status = models.CharField(verbose_name="Статус", max_length=50)
    response = models.TextField(verbose_name="Ответ сервера")
    mailing_list = models.ForeignKey(
        MailingList, verbose_name="Рассылка", on_delete=models.CASCADE
    )
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"id:{self.mailing_list.pk}|{self.date} | {self.status} | {self.response} | {self.owner.username}"

    class Meta:
        verbose_name = "Состояние рассылки"
        verbose_name_plural = "Состояния рассылок"
        ordering = ["status", "date"]
        permissions = [
            ("can_view_attempts", "Can view sent attempts"),
        ]


class RecipientsListUpload(models.Model):
    # Поле для привязки файла. upload_to определяет подпапку внутри MEDIA_ROOT.
    file = models.FileField(upload_to='recipients_lists/')
    # Опционально: добавим поле с именем файла и датой загрузки
    uploaded_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)
    def __str__(self):
        return self.file.name
