from django.contrib import admin
from .models import MailingList, Recipient, Message, SendAttempt


# Register your models here.
@admin.register(MailingList)
class MailingListAdmin(admin.ModelAdmin):
    list_display = ("message", "status", "date_first_sent", "date_last_sent")
    list_filter = ("status", "date_first_sent", "date_last_sent")
    search_fields = ("message", "recipients", "date_first_sent", "date_last_sent")


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ("email", "title")
    search_fields = ("email", "title")
    list_filter = ("email", "title")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("title",)
    search_fields = ("title",)
    list_filter = ("title",)


@admin.register(SendAttempt)
class SendAttemptAdmin(admin.ModelAdmin):
    list_display = ("date", "status", "response", "mailing_list")
    list_filter = ("status", "date", "mailing_list")
    search_fields = ("date", "mailing_list", "status")
