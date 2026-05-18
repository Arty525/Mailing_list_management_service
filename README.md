# Сбор компаний Северодвинска (Tochka + API Checko)

Программа собирает список юридических лиц с [check.tochka.com](https://check.tochka.com/region/severodvinsk/), 
сохраняет в JSON, затем по каждому ОГРН запрашивает данные через [API Checko](https://checko.ru/integration/api) и формирует Excel.

## Установка

```bash
cd company_scraper
pip install -r requirements.txt
```

## Настройка API-ключа

1. Скопируйте `.env.example` в `.env` (если файла `.env` ещё нет).
2. Укажите свой ключ в `.env`:

```env
CHECKO_API_KEY=ваш_ключ_здесь
```

Ключ можно получить в личном кабинете Checko в разделе API.

## Запуск

Полный цикл (все страницы региона + API по каждому ОГРН):

```bash
python scraper.py
```

Тест:

```bash
python scraper.py --max-pages 1 --max-companies 5 --delay 0.5
```

Только дозагрузить контакты через API для существующего JSON:

```bash
python scraper.py --skip-tochka
```

Только пересобрать Excel:

```bash
python scraper.py --only-excel
```

## Результаты

| Файл | Описание |
|------|----------|
| `companies.json` | Данные Tochka + полный ответ API Checko в поле `checko_api` |
| `companies.xlsx` | Название, адрес, телефон, email |

## Примечания

- Каждый запрос к API Checko расходует баланс — следите за полем `balance` в ответе.
- Email и телефон есть не у всех организаций.
- Пауза `--delay` снижает риск ограничений со стороны Tochka при парсинге списка.
