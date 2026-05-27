# sender/management/commands/recipients_to_excel.py

import os
from pathlib import Path

import openpyxl
from django.core.management import BaseCommand
from openpyxl.styles import Alignment, Font, PatternFill

from sender.models import MailingList, Recipient
from users.models import CustomUser

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Command(BaseCommand):
    help = "Выгружает список получателей в xlsx файл."

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="Email пользователя")
        parser.add_argument(
            "--force", action="store_true", help="Выполнить без подтверждения"
        )

    def handle(self, *args, **options):
        # 1. Определяем email пользователя
        if options["email"]:
            owner_email = options["email"]
        else:
            owner_email = input("Введите email пользователя, чей список получателей нужно сохранить: ")

        # 2. Проверяем существование пользователя
        try:
            owner = CustomUser.objects.get(email=owner_email)
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR("Пользователь не найден"))
            return

        self.stdout.write(f"Пользователь {owner.email} найден.")

        # 3. Получаем получателей
        recipients = Recipient.objects.filter(owner=owner)
        if not recipients.exists():
            self.stdout.write(self.style.WARNING("У этого пользователя нет получателей."))
            return

        self.stdout.write(f"Найдено {recipients.count()} получателей.")

        # 4. Подтверждение (только если не указан --force)
        if not options["force"]:
            confirm = input("Сохранить список? y/n: ")
            if confirm.lower() != "y":
                self.stdout.write("Команда отменена")
                return

        # 5. Создаём Excel-файл
        file_name = f"Список получателей ({owner.email}).xlsx"
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(exist_ok=True)          # создаём папку data, если её нет
        file_path = data_dir / file_name

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Получатели"

        # Заголовки
        headers = ["№", "Email", "Название", "Комментарий", "Статус", "Последняя рассылка", "Рассылки"]
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        # Цвета для заливки
        green_fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")  # светло-зелёный
        red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")    # красный

        for row_idx, recipient in enumerate(recipients, start=2):
            # Определяем, были ли рассылки
            has_mailings = MailingList.objects.filter(recipients=recipient).exists()
            # Проверяем активность (предполагается булево поле is_active; можно заменить на recipient.status)
            is_active = getattr(recipient, "status", True)

            if not is_active:
                row_fill = red_fill
            elif has_mailings:
                row_fill = green_fill
            else:
                row_fill = None

            # Собираем список рассылок
            mailing_titles = MailingList.objects.filter(recipients=recipient).values_list(
                "message__title", flat=True
            )
            # Форматируем дату последней отправки
            last_send = recipient.last_send
            if last_send:
                last_send = last_send.strftime("%d.%m.%Y %H:%M:%S")

            cells_data = [
                row_idx - 1,                     # №
                recipient.email,
                recipient.title,
                recipient.comment or "",
                recipient.status,
                last_send or "",
                ", ".join(mailing_titles) or "",
            ]

            # Записываем ячейки и применяем заливку
            for col_idx, value in enumerate(cells_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                if row_fill:
                    cell.fill = row_fill

        # Автоматическая ширина колонок
        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            adjusted_width = min(max_length + 5, 50)
            ws.column_dimensions[col_letter].width = adjusted_width

        wb.save(file_path)
        self.stdout.write(self.style.SUCCESS(f"Файл сохранён: {file_path}"))