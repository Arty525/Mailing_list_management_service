import json
from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    DeleteView,
)

from .forms import RecipientForm, MessageForm, MailingListForm, RecipientsListUpload, UploadFileForm
from .models import Recipient, Message, MailingList, SendAttempt
from dotenv import load_dotenv
from django.core.management import call_command
from django.http import JsonResponse
from django.core.management import call_command
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt  # если нужно, но лучше с csrf
import sys
from io import StringIO

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=BASE_DIR / ".env")


@login_required
def run_command_recipients_to_excel(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается.'}, status=405)

    try:
        # Перенаправляем вывод команды, чтобы не засорять консоль
        out = StringIO()
        call_command('recipients_to_excel', email=request.user.email, force=True, stdout=out)
        output = out.getvalue()
        return JsonResponse({'status': 'success', 'message': 'Команда запущена.', 'output': output})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
def upload_file(request):
    form = UploadFileForm(request.POST, request.FILES)
    if request.method == "GET":
        form.is_valid()
        return render(request, 'sender/recipients/add_from_file.html', {'form': form})
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']

            # Читаем и валидируем JSON
            try:
                data = json.load(uploaded_file)  # загружаем напрямую из файла в памяти
            except json.JSONDecodeError:
                form.add_error('file', 'Файл должен содержать корректный JSON')
                return render(request, 'sender/recipients/add_from_file.html', {'form': form})

            # Обрабатываем каждого получателя
            created_count = 0
            for recipient_data in data:
                email = recipient_data.get('email')
                if not email:
                    continue  # пропускаем записи без email

                # Безопасно получаем адрес из вложенного словаря
                address = None
                try:
                    address = recipient_data['checko_api']['data']['ЮрАдрес']['АдресРФ']
                except (KeyError, TypeError):
                    address = ''  # или оставить None

                # Используем get_or_create для избежания дублей
                obj, created = Recipient.objects.get_or_create(
                    email=email,
                    defaults={
                        'title': recipient_data.get('name', ''),
                        'comment': address,
                        'owner': request.user
                    }
                )
                if created:
                    created_count += 1

            # Добавим сообщение об успехе (через messages framework)
            from django.contrib import messages
            messages.success(request, f'Импортировано {created_count} новых получателей.')
            return redirect('sender:list_recipients')
        else:
            return render(request, 'sender/recipients/add_from_file.html', {'form': form})
    else:
        form = RecipientsListUpload()
    return render(request, 'sender/recipients/add_from_file.html', {'form': form})

class MainView(ListView):
    model = MailingList
    template_name = "sender/index.html"

    def get_context_data(self, *, object_list=None, **kwargs):
        active_mailing_lists = MailingList.objects.filter(status="started")
        mailing_lists = MailingList.objects.all()
        unique_recipients = Recipient.objects.all()
        context = {
            "mailing_lists": mailing_lists.count(),
            "active_mailing_lists": active_mailing_lists.count(),
            "unique_recipients": unique_recipients.count(),
        }
        return context


class RecipientCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Recipient
    form_class = RecipientForm
    template_name = "sender/recipients/add.html"
    login_url = reverse_lazy("users:login")

    def has_permission(self):
        if self.request.user.is_staff and not self.request.user.is_superuser:
            return HttpResponseForbidden(
                "У вас нет прав для добавления новых получателей рассылок"
            )
        return True

    def get_success_url(self):
        return reverse_lazy("sender:list_recipients")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class RecipientUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Recipient
    form_class = RecipientForm
    template_name = "sender/recipients/update.html"
    login_url = reverse_lazy("users:login")

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user:
            return True
        return HttpResponseForbidden(
            "У вас нет прав для редактирования данных этого получателя"
        )

    def get_success_url(self):
        return reverse_lazy("sender:recipient", kwargs={"pk": self.object.pk})


class RecipientListView(LoginRequiredMixin, ListView):
    model = Recipient
    template_name = "sender/recipients/list.html"
    context_object_name = "recipients"

    def get_queryset(self):
        queryset = cache.get(f"recipients:{self.request.user.pk}")
        if not queryset:
            if self.request.user.has_perm("sender.can_view_recipient"):
                queryset = Recipient.objects.all()
            else:
                queryset = Recipient.objects.filter(owner=self.request.user)
            cache.set(f"recipients:{self.request.user.pk}", queryset, 1 * 1)
        return queryset


class RecipientView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Recipient
    template_name = "sender/recipients/recipient.html"
    context_object_name = "recipient"
    login_url = reverse_lazy("users:login")
    permission_required = "sender.can_view_recipient"

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user:
            return True
        return super().has_permission()


class RecipientDeleteView(LoginRequiredMixin, DeleteView):
    model = Recipient
    template_name = "sender/recipients/delete.html"
    success_url = reverse_lazy("sender:list_recipients")
    login_url = reverse_lazy("users:login")

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user:
            return True
        return HttpResponseForbidden("У вас нет прав для удаления этого получателя")


class MessageCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Message
    template_name = "sender/message/add.html"
    form_class = MessageForm
    login_url = reverse_lazy("users:login")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def has_permission(self):
        if self.request.user.is_staff and not self.request.user.is_superuser:
            return False
        return True

    def get_success_url(self):
        return reverse_lazy("sender:message", kwargs={"pk": self.object.pk})


class MessageUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Message
    template_name = "sender/message/update.html"
    form_class = MessageForm
    login_url = reverse_lazy("users:login")

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user or self.request.user.is_superuser:
            return True
        return HttpResponseForbidden("У вас нет прав для изменения этого сообщения")

    def get_success_url(self):
        return reverse_lazy("sender:message", kwargs={"pk": self.object.pk})


class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = "sender/message/list.html"
    context_object_name = "messages"
    login_url = reverse_lazy("users:login")

    def get_queryset(self):
        queryset = cache.get(f"messages:{self.request.user.pk}")
        if not queryset:
            if self.request.user.has_perm("sender.can_view_message"):
                queryset = Message.objects.all()
            else:
                queryset = Message.objects.filter(owner=self.request.user)
            cache.set(f"messages:{self.request.user.pk}", queryset, 1 * 1)
        return queryset


class MessageDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Message
    template_name = "sender/message/delete.html"
    success_url = reverse_lazy("sender:messages_list")
    login_url = reverse_lazy("users:login")

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user or self.request.user.is_superuser:
            return True
        return HttpResponseForbidden("У вас нет прав для удаления этого сообщения")


class MessageDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Message
    template_name = "sender/message/message.html"
    context_object_name = "message"
    login_url = reverse_lazy("users:login")
    permission_required = "sender.can_view_message"

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user:
            return True
        return super().has_permission()


class MailingListCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = MailingList
    template_name = "sender/mailing_list/add.html"
    form_class = MailingListForm

    def has_permission(self):
        if self.request.user.is_staff and not self.request.user.is_superuser:
            return HttpResponseForbidden("У вас нет прав для создания новой рассылки")
        else:
            return True

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("sender:mailing_list", kwargs={"pk": self.object.pk})


class MailingListUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = MailingList
    template_name = "sender/mailing_list/update.html"
    form_class = MailingListForm
    login_url = reverse_lazy("users:login")

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user or self.request.user.is_superuser:
            return True
        return HttpResponseForbidden("У вас нет прав для редактирования этой рассылки")

    def get_success_url(self):
        return reverse_lazy("sender:mailing_list", kwargs={"pk": self.object.pk})


class MailingListDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = MailingList
    template_name = "sender/mailing_list/delete.html"
    success_url = reverse_lazy("sender:mailing_lists")
    login_url = reverse_lazy("users:login")

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user or self.request.user.is_superuser:
            return True
        return False


class MailingListDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = MailingList
    template_name = "sender/mailing_list/mailing_list.html"
    permission_required = "sender.can_view_mailing_list"

    def has_permission(self):
        instance = self.get_object()
        if instance.owner == self.request.user:
            return True
        return super().has_permission()

    def get_context_data(self, *, object_list=None, **kwargs):
        mailing_list = MailingList.objects.get(pk=self.object.pk)
        recipients = mailing_list.recipients.all()
        context = {"mailing_list": mailing_list, "recipients": recipients}
        return context


class MailingListsListView(LoginRequiredMixin, ListView):
    model = MailingList
    template_name = "sender/mailing_list/list.html"
    context_object_name = "mailing_lists"

    def get_queryset(self):
        queryset = cache.get(f"mailing_lists:{self.request.user.pk}")
        if not queryset:
            if self.request.user.has_perm("sender.can_view_mailing_list"):
                queryset = MailingList.objects.all()
            else:
                queryset = MailingList.objects.filter(owner=self.request.user)
            cache.set(f"mailing_lists:{self.request.user.pk}", queryset, 1 * 1)
        return queryset


class RunSend(LoginRequiredMixin, View):
    success_url = reverse_lazy("sender:mailing_lists")

    def post(self, request, *args, **kwargs):
        mailing_list = get_object_or_404(MailingList, id=self.kwargs["pk"])
        if mailing_list.owner == request.user or request.user.is_superuser:
            mailing_list.send()
        else:
            raise HttpResponseForbidden("У вас нет права запускать эту рассылку")
        return redirect(self.success_url)


class ChangeMailingListStatus(LoginRequiredMixin, View):
    def post(self, request, pk):
        mailing_list = get_object_or_404(MailingList, id=pk)
        if request.user.has_perm("sender.can_turn_off"):
            mailing_list.is_active = not mailing_list.is_active
            mailing_list.save()
            return redirect(reverse_lazy("sender:mailing_lists"))
        return HttpResponseForbidden("У вас нет прав для отключения этой рассылки")


class SendAttemptListView(LoginRequiredMixin, ListView):
    model = SendAttempt
    template_name = "sender/sent_attempt/list.html"
    context_object_name = "sent_attempt_list"

    def get_queryset(self):
        queryset = cache.get(f"sent_attempts:{self.request.user.pk}")
        if not queryset:
            if self.request.user.has_perm("sender.can_view_attempts"):
                queryset = SendAttempt.objects.all()
            else:
                queryset = SendAttempt.objects.filter(owner=self.request.user)
            cache.set(f"sent_attempts:{self.request.user.pk}", queryset, 1 * 1)
        print(f"Данные из кэша: {queryset}")
        return queryset
