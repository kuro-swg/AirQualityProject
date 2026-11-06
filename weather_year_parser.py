
import calendar
import re
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "data" / "almaty_weather_year.csv"

START = "2025-11-01"
END = "2026-10-31"

MONTH_NAMES = [
    "", "январь", "февраль", "март", "апрель",
    "май", "июнь", "июль", "август",
    "сентябрь", "октябрь", "ноябрь", "декабрь"
]

# Два месяца 2025 года и десять месяцев 2026
MONTHS = (
    [(2025, 11), (2025, 12)]
    + [(2026, m) for m in range(1, 11)]
)


def parse_number(text):
    text = text.strip()
    text = text.replace(",", ".").replace("−", "-")
    text = text.replace("+", "")

    try:
        return float(text)
    except ValueError:
        return None


def parse_month(driver, year, month):
    """Извлекает данные одного месяца из HTML."""
    url = (
        "https://www.pogodaiklimat.ru/monitor.php"
        f"?id=36870&month={month}&year={year}"
    )

    driver.get(url)

    WebDriverWait(driver, 15).until(
        lambda d: len(
            d.find_elements(By.TAG_NAME, "table")
        ) > 0
    )

    # Убеждаемся, что сайт открыл нужный месяц
    page_text = driver.find_element(
        By.TAG_NAME, "body"
    ).text[:2000].lower()

    expected_heading = f"{MONTH_NAMES[month]} {year}"

    if expected_heading not in page_text:
        raise ValueError(
            f"На странице нет заголовка {expected_heading}"
        )

    days_in_month = calendar.monthrange(year, month)[1]
    best_records = []

    for table in driver.find_elements(By.TAG_NAME, "table"):
        records = []

        for row in table.find_elements(By.TAG_NAME, "tr"):
            cells = row.find_elements(By.XPATH, "./td")
            values = [c.text.strip() for c in cells]

            if len(values) != 6:
                continue

            if not re.fullmatch(r"\d{1,2}", values[0]):
                continue

            day = int(values[0])

            if not 1 <= day <= days_in_month:
                continue

            nums = [parse_number(v) for v in values[1:]]

            # Не считаем пустую строку наблюдением
            if all(v is None for v in nums):
                continue

            t_min, t_mean, t_max = nums[:3]

            # Проверка логики температур
            if all(v is not None for v in nums[:3]):
                if not t_min <= t_mean <= t_max:
                    print(f"  Некорректные температуры: день {day}")
                    continue

            records.append({
                "date": f"{year}-{month:02d}-{day:02d}",
                "city": "Almaty",
                "temp_min_c": nums[0],
                "temp_mean_c": nums[1],
                "temp_max_c": nums[2],
                "temp_anomaly_c": nums[3],
                "precipitation_mm": nums[4],
                "source": "Pogoda i Klimat"
            })

        if len(records) > len(best_records):
            best_records = records

    return best_records


# --- СБОР ДАННЫХ ---

driver = webdriver.Firefox()
all_records = []
failed_months = []

try:
    for year, month in MONTHS:
        print(f"\nОбрабатываем {month:02d}.{year}")

        try:
            records = parse_month(driver, year, month)

            all_records.extend(records)

            expected = calendar.monthrange(year, month)[1]
            print(f"Получено: {len(records)} из {expected} дней")

            if len(records) < expected:
                failed_months.append(f"{year}-{month:02d}")

        except Exception as error:
            print("Ошибка:", error)
            failed_months.append(f"{year}-{month:02d}")

        # Не отправляем запросы слишком часто
        time.sleep(1)

finally:
    driver.quit()


if not all_records:
    raise SystemExit("Не удалось собрать данные.")

# --- ОЧИСТКА ---

df = pd.DataFrame(all_records)

df = df.drop_duplicates(
    subset=["date", "city", "source"],
    keep="last"
)

df = df.sort_values("date").reset_index(drop=True)

# Проверяем осадки
df.loc[
    df["precipitation_mm"] < 0,
    "precipitation_mm"
] = float("nan")

# Отмечаем полностью заполненные строки
numeric_columns = [
    "temp_min_c",
    "temp_mean_c",
    "temp_max_c",
    "temp_anomaly_c",
    "precipitation_mm"
]

df["is_complete"] = df[numeric_columns].notna().all(axis=1)

# --- ПРОВЕРКА ПЕРИОДА ---

all_dates = set(
    pd.date_range(START, END).strftime("%Y-%m-%d")
)

missing_dates = sorted(all_dates - set(df["date"]))

# --- СОХРАНЕНИЕ ---

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(
    OUTPUT,
    index=False,
    encoding="utf-8-sig"
)

# --- ОТЧЁТ ---

print("\n========== ИТОГ ==========")
print("Всего записей:", len(df))
print("Ожидалось дат:", len(all_dates))
print("Полных записей:", int(df["is_complete"].sum()))
print("Дубликатов:", df.duplicated(
    subset=["date", "city", "source"]
).sum())

print("Отсутствующих дней:", len(missing_dates))
print("Пропущенные даты:", missing_dates)
print("Проблемные месяцы:", failed_months)

print("\nПропуски по столбцам:")
print(df.isna().sum())

print("\nПервые строки:")
print(df.head().to_string(index=False))

print("\nПоследние строки:")
print(df.tail().to_string(index=False))

print("\nФайл:", OUTPUT)
