# sender/management/commands/recipients_to_excel.py
from django.core.management import BaseCommand
from users.models import CustomUser
from sender.models import Recipient, MailingList
from openpyxl.styles import Font, Alignment
import openpyxl
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Command(BaseCommand):
    help = 'Выгружает список получателей в xlsx файл.'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email пользователя')
        parser.add_argument('--force', action='store_true', help='Выполнить без подтверждения')

    def handle(self, *args, **options):
        # 1. Получаем email пользователя
        if options['email']:
            owner_email = options['email']
        else:
            owner_email = input('Введите email пользователя, чей список получателей нужно сохранить: ')

        try:
            owner = CustomUser.objects.get(email=owner_email)
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR('Пользователь не найден'))
            return

        self.stdout.write(f'Пользователь {owner.email} найден.')

        recipients = Recipient.objects.filter(owner=owner)
        if not recipients.exists():
            self.stdout.write(self.style.WARNING('У этого пользователя нет получателей.'))
            return

        self.stdout.write(f'Найдено {recipients.count()} получателей.')

        # 2. Подтверждение (только если не указан --force)
        if not options['force']:
            confirm = input('Сохранить список? y/n: ')
            if confirm.lower() != 'y':
                self.stdout.write('Команда отменена')
                return

        # 3. Генерация Excel
        file_name = f'Список получателей ({owner.email}).xlsx'
        file_path = os.path.join(BASE_DIR, 'data', file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Получатели"

        headers = ['№', 'Email', 'Название', 'Комментарий', 'Статус', 'Последняя рассылка', 'Рассылки']
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        for row_idx, recipient in enumerate(recipients, start=2):
            mailing_list = MailingList.objects.filter(recipients=recipient).values_list('message__title', flat=True)
            last_send = recipient.last_send
            if last_send:
                last_send = last_send.strftime("%d.%m.%Y %H:%M:%S")

            ws.cell(row=row_idx, column=1, value=row_idx - 1)
            ws.cell(row=row_idx, column=2, value=recipient.email)
            ws.cell(row=row_idx, column=3, value=recipient.title)
            ws.cell(row=row_idx, column=4, value=recipient.comment or '')
            ws.cell(row=row_idx, column=5, value=recipient.status)
            ws.cell(row=row_idx, column=6, value=last_send or '')
            ws.cell(row=row_idx, column=7, value=','.join(list(mailing_list)) or '')

        # Автоширина колонок
        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = min(max_length + 5, 50)
            ws.column_dimensions[col_letter].width = adjusted_width

        wb.save(file_path)
        self.stdout.write(self.style.SUCCESS(f'Файл сохранён: {file_path}'))