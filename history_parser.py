
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://cerns.io/kz/almaty/history?range=20d"
OUTPUT = Path(__file__).resolve().parent / "data" / "almaty_october_2026.csv"

def get_number(text):
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)

    if match:
        return float(match.group().replace(",", "."))

    return None


driver = webdriver.Firefox()
results = []

try:
    driver.get(URL)

    # Ожидаем появления строк таблицы
    WebDriverWait(driver, 20).until(
        lambda d: len(
            d.find_elements(By.CSS_SELECTOR, "table tbody tr")
        ) > 0
    )

    table = driver.find_element(By.TAG_NAME, "table")
    rows = table.find_elements(By.TAG_NAME, "tr")

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        values = [cell.text.strip() for cell in cells]

        if len(values) != 7:
            continue

        # Проверяем дату
        try:
            day = datetime.strptime(values[0], "%Y-%m-%d")
        except ValueError:
            continue

        if day.year != 2026 or day.month != 10:
            continue

        # Извлекаем диапазон AQI
        aqi_range = re.search(
            r"(\d+)\s*[-–—]\s*(\d+)", values[2]
        )

        aqi_min = None
        aqi_max = None

        if aqi_range:
            aqi_min = int(aqi_range.group(1))
            aqi_max = int(aqi_range.group(2))

        results.append({
            "date": day.strftime("%Y-%m-%d"),
            "city": "Almaty",
            "aqi": get_number(values[1]),
            "aqi_min": aqi_min,
            "aqi_max": aqi_max,
            "pm25_ug_m3": get_number(values[3]),
            "pm10_ug_m3": get_number(values[4]),
            "hours": get_number(values[5]),
            "stations": get_number(values[6]),
            "source": "CERNS"
        })

finally:
    driver.quit()


if not results:
    print("Данные за октябрь не найдены.")
    raise SystemExit

# Превращаем список словарей в таблицу
df = pd.DataFrame(results)

# Удаляем некорректные отрицательные значения
for col in ["aqi", "aqi_min", "aqi_max",
            "pm25_ug_m3", "pm10_ug_m3"]:
    df.loc[df[col] < 0, col] = float("nan")

# Проверяем часы и количество станций
df.loc[~df["hours"].between(1, 24), "hours"] = float("nan")
df.loc[df["stations"] < 1, "stations"] = float("nan")

# Убираем записи без обоих PM-показателей
df = df.dropna(
    subset=["pm25_ug_m3", "pm10_ug_m3"],
    how="all"
)

# Если файл существует — добавляем старые записи
if OUTPUT.exists():
    old_df = pd.read_csv(OUTPUT)

    if set(old_df.columns) != set(df.columns):
        raise ValueError(
            "Структура старого CSV отличается от новой. "
            "Проверь файл перед объединением."
        )

    df = pd.concat([old_df, df], ignore_index=True)

# Удаляем дубликаты
df = df.drop_duplicates(
    subset=["date", "city", "source"],
    keep="last"
)

# Сортируем по дате
df = df.sort_values("date")

# Сохраняем CSV
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

# Проверяем отсутствующие дни октября
all_dates = set(
    pd.date_range(
        "2026-10-01", "2026-10-31"
    ).strftime("%Y-%m-%d")
)

missing_dates = sorted(all_dates - set(df["date"]))

print("\nПАРСИНГ ЗАВЕРШЁН")
print("Количество записей:", len(df))
print("Дубликатов:", df.duplicated(
    subset=["date", "city", "source"]
).sum())
print("Отсутствующих дней:", len(missing_dates))
print("Пропущенные даты:", missing_dates)

print("\nЧастичные дни:")
print(df.loc[df["hours"] < 24, ["date", "hours"]])

print("\nПервые строки:")
print(df.head().to_string(index=False))

print("\nФайл сохранён:", OUTPUT)
