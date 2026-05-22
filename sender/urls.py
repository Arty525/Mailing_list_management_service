from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    MainView,
    RecipientCreateView,
    RecipientListView,
    RecipientView,
    RecipientDeleteView,
    MessageCreateView,
    MessageUpdateView,
    MessageDeleteView,
    MessageListView,
    MessageDetailView,
    RecipientUpdateView,
    MailingListUpdateView,
    MailingListDeleteView,
    MailingListCreateView,
    MailingListsListView,
    MailingListDetailView,
    RunSend,
    ChangeMailingListStatus,
    SendAttemptListView,
    upload_file, run_command_recipients_to_excel,
)

app_name = "sender"

urlpatterns = (
    [
        # главная
        path("", MainView.as_view(), name="index"),
        # получатели рассылок
        path("recipients/add/", RecipientCreateView.as_view(), name="add_recipient"),
        path('recipients/add_from_file', upload_file, name="add_from_file"),
        path("recipients/list/", RecipientListView.as_view(), name="list_recipients"),
        path(
            "recipients/recipient/<int:pk>", RecipientView.as_view(), name="recipient"
        ),
        path(
            "recipients/delete/<int:pk>",
            RecipientDeleteView.as_view(),
            name="delete_recipient",
        ),
        path(
            "recipients/update/<int:pk>",
            RecipientUpdateView.as_view(),
            name="update_recipient",
        ),
        path('rte_command/', run_command_recipients_to_excel, name='rte_command'),
        # сообщения рассылок
        path("message/add/", MessageCreateView.as_view(), name="add_message"),
        path(
            "message/update/<int:pk>",
            MessageUpdateView.as_view(),
            name="update_message",
        ),
        path(
            "message/delete/<int:pk>",
            MessageDeleteView.as_view(),
            name="delete_message",
        ),
        path("message/list/", MessageListView.as_view(), name="messages_list"),
        path("message/message/<int:pk>", MessageDetailView.as_view(), name="message"),
        # рассылки
        path(
            "mailing_list/list/", MailingListsListView.as_view(), name="mailing_lists"
        ),
        path(
            "mailing_list/update/<int:pk>",
            MailingListUpdateView.as_view(),
            name="mailing_list_update",
        ),
        path(
            "mailing_list/delete/<int:pk>",
            MailingListDeleteView.as_view(),
            name="mailing_list_delete",
        ),
        path(
            "mailing_list/add/",
            MailingListCreateView.as_view(),
            name="add_mailing_list",
        ),
        path(
            "mailing_list/<int:pk>",
            MailingListDetailView.as_view(),
            name="mailing_list",
        ),
        path("mailing_list/<int:pk>/run_send", RunSend.as_view(), name="run_send"),
        path(
            "mailing_list/<int:pk>/turn_off",
            ChangeMailingListStatus.as_view(),
            name="turn_off",
        ),
        # Попытки рассылок
        path(
            "sent_attempt/list/",
            SendAttemptListView.as_view(),
            name="sent_attempts_list",
        ),
    ]
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)
