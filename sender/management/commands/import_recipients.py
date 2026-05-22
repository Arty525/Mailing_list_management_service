from django.core.management import BaseCommand
from users.models import CustomUser
from sender.models import Recipient
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Command(BaseCommand):
    help = 'Загружает список получателей из JSON файла.'

    def handle(self, *args, **options):
        # Открываем и читаем JSON-файл
        path = BASE_DIR / 'data' / 'companies.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Получаем владельца
        owner_email = input('Введите email пользователя, за которым будут закреплены получатели: ')
        try:
            owner = CustomUser.objects.get(email=owner_email)
        except CustomUser.DoesNotExist:
            print('Пользователь не найден')
            sys.exit(0)

        created_count = 0
        for recipient_data in data:
            email = recipient_data.get('email')
            if not email:
                continue  # пропускаем записи без email

            # Безопасно получаем адрес из вложенного словаря
            address = ''
            try:
                address = recipient_data['checko_api']['data']['ЮрАдрес']['АдресРФ']
            except (KeyError, TypeError):
                pass

            # Используем get_or_create для избежания дублей
            obj, created = Recipient.objects.get_or_create(
                email=email,
                defaults={
                    'title': recipient_data.get('name', ''),
                    'comment': address,
                    'owner': owner
                }
            )
            if created:
                created_count += 1

        print(f'Добавлено {created_count} получателей')