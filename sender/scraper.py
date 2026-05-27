#!/usr/bin/env python3
"""
Сбор данных о юрлицах Северодвинска с check.tochka.com,
контактов через API Checko по ОГРН, экспорт в JSON и Excel.
Поддерживает суточный лимит запросов к API (100 по умолчанию).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.styles import Font


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

TOCHKA_REGION_URL = "https://check.tochka.com/region/severodvinsk/"
CHECKO_API_URL = "https://api.checko.ru/v2/company"
DEFAULT_JSON = "data/companies.json"
DEFAULT_EXCEL = "data/companies.xlsx"
DEFAULT_USAGE_FILE = "data/api_usage.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class ScraperError(Exception):
    pass


def load_checko_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("CHECKO_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise SystemExit(
            "Укажите CHECKO_API_KEY в файле .env "
            "(скопируйте .env.example и вставьте свой ключ API Checko)"
        )
    return api_key


def fetch(session: requests.Session, url: str, **kwargs: Any) -> requests.Response:
    response = session.get(url, headers=HEADERS, timeout=60, **kwargs)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response


def parse_total_pages(soup: BeautifulSoup) -> int:
    max_page = 1
    for link in soup.select('a[href*="page="]'):
        href = link.get("href", "")
        match = re.search(r"[?&]page=(\d+)", href)
        if match:
            max_page = max(max_page, int(match.group(1)))
    if max_page > 1:
        return max_page

    text = soup.get_text(" ", strip=True)
    match = re.search(r"Найдено\s+([\d\s]+)\s+организа", text)
    if not match:
        return 1
    total = int(re.sub(r"\s", "", match.group(1)))
    per_page = len(
        {
            m.group(1)
            for a in soup.select('a[href*="/company/"]')
            if (m := re.search(r"/company/(\d{13,15})", a.get("href", "")))
        }
    )
    if per_page <= 0:
        return 1
    return max(1, (total + per_page - 1) // per_page)


def parse_tochka_page(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    companies: list[dict[str, Any]] = []
    seen_ogrn: set[str] = set()

    cards = soup.select("div.company-card, article.company-card, li.company-card")
    if not cards:
        cards = soup.select('[class*="company"], [class*="CompanyCard"]')

    if cards:
        for card in cards:
            company = _parse_company_card(card)
            if company and company["ogrn"] not in seen_ogrn:
                seen_ogrn.add(company["ogrn"])
                companies.append(company)
        if companies:
            return companies

    return _parse_tochka_fallback(soup, seen_ogrn)


def _parse_company_card(card: BeautifulSoup) -> dict[str, Any] | None:
    link = card.select_one('a[href*="/company/"]')
    ogrn = None
    if link and link.get("href"):
        m = re.search(r"/company/(\d+)/?", link["href"])
        if m:
            ogrn = m.group(1)
    text = card.get_text("\n", strip=True)
    if not ogrn:
        m = re.search(r"ОГРН[:\s]*(\d{13,15})", text, re.I)
        if m:
            ogrn = m.group(1)
    if not ogrn:
        return None

    name = link.get_text(strip=True) if link else ""
    if not name:
        name = _extract_field(text, "name") or ""

    return {
        "name": name,
        "ogrn": ogrn,
        "inn": _extract_labeled(text, "ИНН"),
        "kpp": _extract_labeled(text, "КПП"),
        "legal_address": _extract_labeled(text, "Юр. адрес")
        or _extract_labeled(text, "Юридический адрес"),
        "status": _extract_labeled(text, "Статус") or _guess_status(text),
        "registration_date": _extract_labeled(text, "Дата регистрации"),
        "tochka_url": urljoin("https://check.tochka.com", f"/company/{ogrn}/"),
    }


def _parse_tochka_fallback(
    soup: BeautifulSoup, seen_ogrn: set[str]
) -> list[dict[str, Any]]:
    """Разбор страницы по ссылкам /company/OGRN/ и соседнему тексту."""
    companies: list[dict[str, Any]] = []
    links = soup.select('a[href*="/company/"]')

    for link in links:
        href = link.get("href", "")
        m = re.search(r"/company/(\d{13,15})/?", href)
        if not m:
            continue
        ogrn = m.group(1)
        if ogrn in seen_ogrn:
            continue
        seen_ogrn.add(ogrn)

        name = link.get_text(strip=True)
        block_text = _nearest_block_text(link)
        if not name and block_text:
            name = ""

        companies.append(
            {
                "name": name,
                "ogrn": ogrn,
                "inn": _extract_labeled(block_text, "ИНН"),
                "kpp": _extract_labeled(block_text, "КПП"),
                "legal_address": _extract_labeled(block_text, "Юр. адрес")
                or _extract_labeled(block_text, "Юридический адрес"),
                "status": _guess_status(block_text),
                "registration_date": _extract_labeled(
                    block_text, "Дата регистрации"
                ),
                "tochka_url": urljoin("https://check.tochka.com", href),
            }
        )

    if companies:
        return companies

    return _parse_tochka_text_blocks(soup.get_text("\n"), seen_ogrn)


def _parse_tochka_text_blocks(
    page_text: str, seen_ogrn: set[str]
) -> list[dict[str, Any]]:
    companies: list[dict[str, Any]] = []
    blocks = re.split(r"(?=Действующая компания|Ликвидирован|В стадии)", page_text)

    for block in blocks:
        ogrn_match = re.search(r"ОГРН[:\s]*(\d{13,15})", block, re.I)
        if not ogrn_match:
            continue
        ogrn = ogrn_match.group(1)
        if ogrn in seen_ogrn:
            continue
        seen_ogrn.add(ogrn)

        companies.append(
            {
                "name": "",
                "ogrn": ogrn,
                "inn": _extract_labeled(block, "ИНН"),
                "kpp": _extract_labeled(block, "КПП"),
                "legal_address": _extract_labeled(block, "Юр. адрес"),
                "status": _guess_status(block),
                "registration_date": _extract_labeled(
                    block, "Дата регистрации"
                ),
                "tochka_url": f"https://check.tochka.com/company/{ogrn}/",
            }
        )
    return companies


def _nearest_block_text(link: BeautifulSoup) -> str:
    parent = link.parent
    for _ in range(6):
        if parent is None:
            break
        text = parent.get_text("\n", strip=True)
        if "ОГРН" in text or "ИНН" in text:
            return text
        parent = parent.parent
    return link.parent.get_text("\n", strip=True) if link.parent else ""


def _extract_labeled(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*[:：]\s*(.+?)(?:\n|$)"
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else ""


def _extract_field(text: str, field: str) -> str:
    return ""


def _guess_status(text: str) -> str:
    if "Ликвидир" in text:
        return "Ликвидирована"
    if "Действующ" in text:
        return "Действующая"
    return ""


def scrape_tochka(
    session: requests.Session,
    max_pages: int | None = None,
    delay: float = 1.0,
) -> list[dict[str, Any]]:
    all_companies: list[dict[str, Any]] = []
    seen: set[str] = set()

    response = fetch(session, TOCHKA_REGION_URL)
    first_soup = BeautifulSoup(response.text, "lxml")
    total_pages = parse_total_pages(first_soup)
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    for page in range(1, total_pages + 1):
        url = TOCHKA_REGION_URL if page == 1 else f"{TOCHKA_REGION_URL}?page={page}"
        if page > 1:
            response = fetch(session, url)
        page_companies = parse_tochka_page(response.text)

        added = 0
        for company in page_companies:
            if company["ogrn"] in seen:
                continue
            seen.add(company["ogrn"])
            all_companies.append(company)
            added += 1

        print(f"Страница {page}/{total_pages}: +{added} (всего {len(all_companies)})")
        if page < total_pages:
            time.sleep(delay)

        if added == 0 and page > 1:
            break

    return all_companies


def fetch_checko_company(
    session: requests.Session, api_key: str, ogrn: str, inn: str = None
) -> dict[str, Any]:
    # Приоритет: используем ИНН, если он есть, иначе ОГРН
    identifier = inn if inn else ogrn
    param_key = "inn" if inn else "ogrn"

    response = session.get(
        CHECKO_API_URL,
        params={"key": api_key, param_key: identifier},
        timeout=60,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()

    # Проверяем, есть ли в ответе данные
    data = payload.get("data")
    if not data:
        raise ScraperError(
            f"API не вернул данные для {param_key.upper()} {identifier}."
        )

    # Проверяем, нет ли ошибки в метаданных
    meta = payload.get("meta") or {}
    if meta.get("status") == "error":
        raise ScraperError(meta.get("message") or "Неизвестная ошибка API Checko")

    # Проверяем, что ответ не пустой
    if not data:
        raise ScraperError(f"API вернул пустой ответ для {param_key.upper()} {identifier}.")

    return payload

def parse_checko_api(data: dict[str, Any]) -> dict[str, Any]:
    contacts = data.get("Контакты") or {}
    phones = _unique_nonempty([str(p).strip() for p in (contacts.get("Тел") or [])])
    emails = _unique_nonempty(
        [str(e).strip().lower() for e in (contacts.get("Емэйл") or [])]
    )

    yur = data.get("ЮрАдрес") or {}
    legal_address = (yur.get("АдресРФ") or "").strip()
    if not legal_address:
        parts = [yur.get("НасПункт"), yur.get("АдресРФ")]
        legal_address = ", ".join(str(p).strip() for p in parts if p)

    status_obj = data.get("Статус") or {}
    name_short = (data.get("НаимСокр") or "").strip()
    name_full = (data.get("НаимПолн") or "").strip()
    ogrn = str(data.get("ОГРН") or "").strip()

    return {
        "name": name_short or name_full,
        "name_full": name_full,
        "inn": str(data.get("ИНН") or "").strip(),
        "kpp": str(data.get("КПП") or "").strip(),
        "ogrn": ogrn,
        "legal_address": legal_address,
        "status": (status_obj.get("Наим") or "").strip(),
        "phone": phones[0] if phones else "",
        "phones": phones,
        "email": emails[0] if emails else "",
        "emails": emails,
        "website": (contacts.get("ВебСайт") or "").strip(),
        "checko_url": f"https://checko.ru/company/{ogrn}" if ogrn else "",
    }


def _unique_nonempty(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


# ---------- Управление суточным лимитом запросов ----------
def load_api_usage(usage_path: Path) -> tuple[str, int]:
    """Загружает дату и количество использованных запросов из файла."""
    if not usage_path.exists():
        return datetime.now(timezone.utc).strftime("%Y-%m-%d"), 0
    try:
        data = json.loads(usage_path.read_text(encoding="utf-8"))
        date = data.get("date", "")
        count = data.get("count", 0)
        return date, count
    except (json.JSONDecodeError, OSError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d"), 0


def save_api_usage(usage_path: Path, date: str, count: int) -> None:
    """Сохраняет дату и количество использованных запросов в файл."""
    usage_path.write_text(
        json.dumps({"date": date, "count": count}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def acquire_api_request(usage_path: Path, daily_limit: int) -> bool:
    """
    Проверяет, не превышен ли суточный лимит.
    Если лимит не превышен, увеличивает счётчик на 1 и возвращает True.
    Иначе возвращает False.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    saved_date, used = load_api_usage(usage_path)

    if saved_date != today:
        used = 0
        saved_date = today

    if used >= daily_limit:
        return False

    # лимит не достигнут – увеличиваем счётчик и сохраняем
    save_api_usage(usage_path, saved_date, used + 1)
    return True


# ------------------------------------------------

def enrich_with_checko(
    session: requests.Session,
    api_key: str,
    companies: list[dict[str, Any]],
    delay: float = 0.3,
    skip_existing: bool = True,
    max_companies: int | None = None,
    json_path: Path | None = None,
    daily_limit: int = 100,
    usage_path: Path = Path(DEFAULT_USAGE_FILE),
) -> None:
    """
    Обогащает компании данными из API Checko.
    Учитывает суточный лимит запросов daily_limit, храня счётчик в usage_path.
    """
    processed = 0
    # последний известный счётчик запросов за сегодня (для информационных сообщений)
    for index, company in enumerate(companies, start=1):
        if max_companies is not None and processed >= max_companies:
            break

        # Пропускаем уже обработанные компании
        if skip_existing and company.get("checko_api_fetched"):
            continue

        # Проверяем суточный лимит перед каждым запросом
        if not acquire_api_request(usage_path, daily_limit):
            print(
                f"Достигнут суточный лимит запросов ({daily_limit}). "
                "Дальнейшие вызовы API пропущены."
            )
            break

        processed += 1
        ogrn = company["ogrn"]
        print(f"[{index}/{len(companies)}] API Checko — ОГРН {ogrn}")

        try:
            payload = fetch_checko_company(session, api_key, ogrn)
            parsed = parse_checko_api(payload["data"])
            company["checko_api"] = payload
            company["checko_api_fetched"] = True
            company["checko_url"] = parsed["checko_url"]
            company["phone"] = parsed["phone"]
            company["phones"] = parsed["phones"]
            company["email"] = parsed["email"]
            company["emails"] = parsed["emails"]
            company["website"] = parsed.get("website", "")
            if parsed["name"]:
                company["checko_name"] = parsed["name"]
                if not company.get("name"):
                    company["name"] = parsed["name"]
            if parsed["legal_address"]:
                company["checko_legal_address"] = parsed["legal_address"]
            if parsed["inn"] and not company.get("inn"):
                company["inn"] = parsed["inn"]
            if parsed["status"] and not company.get("status"):
                company["status"] = parsed["status"]
            meta = payload.get("meta") or {}
            balance = meta.get("balance")
            if balance is not None and index % 50 == 0:
                print(f"  баланс API: {balance} руб.")
        except (requests.RequestException, ScraperError, ValueError) as exc:
            company["checko_error"] = str(exc)
            company["checko_api_fetched"] = True
            print(f"  ошибка: {exc}")

        if json_path is not None and index % 10 == 0:
            save_json(companies, json_path)

        time.sleep(delay)


def save_json(companies: list[dict[str, Any]], path: Path) -> None:
    path.write_text(
        json.dumps(companies, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON сохранён: {path}")


def load_json(path: Path) -> list[dict[str, Any]]:
    companies = json.loads(path.read_text(encoding="utf-8"))
    # Миграция старых данных: если у компании есть checko_api, но нет флага fetched – проставляем
    for company in companies:
        if "checko_api" in company and not company.get("checko_api_fetched"):
            company["checko_api_fetched"] = True
    return companies


def export_excel(companies: list[dict[str, Any]], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Компании"

    headers = [
        "Название",
        "ОГРН",
        "Юридический адрес",
        "Телефон",
        "Email",
        "ИНН",
        "Статус",
        "Ссылка checko.ru",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for company in companies:
        name = (
            company.get("name")
            or company.get("checko_name")
            or ""
        )
        address = (
            company.get("legal_address")
            or company.get("checko_legal_address")
            or ""
        )
        ws.append(
            [
                name,
                company.get("ogrn", ""),
                address,
                company.get("phone", ""),
                company.get("email", ""),
                company.get("inn", ""),
                company.get("status", ""),
                company.get("checko_url", ""),
            ]
        )

    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column_letter].width = min(max_length + 2, 60)

    wb.save(path)
    print(f"Excel сохранён: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сбор компаний Северодвинска (Tochka + Checko) → JSON + Excel",
    )
    parser.add_argument(
        "--json",
        default=DEFAULT_JSON,
        help=f"Путь к JSON (по умолчанию {DEFAULT_JSON})",
    )
    parser.add_argument(
        "--excel",
        default=DEFAULT_EXCEL,
        help=f"Путь к Excel (по умолчанию {DEFAULT_EXCEL})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Ограничить число страниц Tochka (для теста)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Пауза между запросами, сек",
    )
    parser.add_argument(
        "--skip-tochka",
        action="store_true",
        help="Не собирать Tochka, только обогатить JSON контактами",
    )
    parser.add_argument(
        "--skip-checko",
        action="store_true",
        help="Не запрашивать API Checko",
    )
    parser.add_argument(
        "--only-excel",
        action="store_true",
        help="Только пересобрать Excel из существующего JSON",
    )
    parser.add_argument(
        "--max-companies",
        type=int,
        default=None,
        help="Сколько компаний обогатить через API Checko",
    )
    parser.add_argument(
        "--daily-limit",
        type=int,
        default=100,
        help="Суточный лимит запросов к API Checko (по умолчанию 100)",
    )
    parser.add_argument(
        "--usage-file",
        default=DEFAULT_USAGE_FILE,
        help=f"Файл для хранения счётчика запросов (по умолчанию {DEFAULT_USAGE_FILE})",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    json_path = Path(args.json)
    excel_path = Path(args.excel)
    usage_path = Path(args.usage_file)

    if args.only_excel:
        if not json_path.exists():
            raise SystemExit(f"Файл не найден: {json_path}")
        companies = load_json(json_path)
        export_excel(companies, excel_path)
        return

    session = requests.Session()

    if args.skip_tochka and json_path.exists():
        companies = load_json(json_path)
        print(f"Загружено из JSON: {len(companies)} записей")
    elif args.skip_tochka:
        raise SystemExit("Нужен существующий JSON или уберите --skip-tochka")
    else:
        print("Сбор данных с check.tochka.com …")
        companies = scrape_tochka(
            session, max_pages=args.max_pages, delay=args.delay
        )
        save_json(companies, json_path)

    if not args.skip_checko:
        api_key = load_checko_api_key()
        print("Запрос контактов через API Checko …")
        enrich_with_checko(
            session,
            api_key,
            companies,
            delay=args.delay,
            max_companies=args.max_companies,
            json_path=json_path,
            daily_limit=args.daily_limit,
            usage_path=usage_path,
        )
        save_json(companies, json_path)

    export_excel(companies, excel_path)
    print("Готово.")


if __name__ == "__main__":
    main()