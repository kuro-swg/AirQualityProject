
import re
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://pollution-alert.com/en/kazakhstan/pollution/geo-1526384/almaty"

OUTPUT = (
    Path(__file__).resolve().parent
    / "data"
    / "pollution_alert_october_2026.csv"
)

# Названия показателей в итоговом CSV
POLLUTANTS = {
    "PM2.5": "pm25_ug_m3",
    "PM10": "pm10_ug_m3",
    "O3": "o3_ug_m3",
    "NO2": "no2_ug_m3",
    "SO2": "so2_ug_m3",
    "CO": "co_ug_m3"
}

def clean_label(text):
    """Приводим названия к одному формату."""
    text = text.translate(
        str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
    )
    return re.sub(r"\s+", "", text).upper()


def parse_number(text):
    """Превращаем значение ячейки в число."""
    text = text.strip().replace(",", "").replace(" ", "")

    try:
        return float(text)
    except ValueError:
        return None


def read_cells(row):
    """Получаем текст всех ячеек строки."""
    cells = row.find_elements(By.CSS_SELECTOR, "th, td")

    return [
        (cell.get_attribute("textContent") or "").strip()
        for cell in cells
    ]


def find_history_table(driver):
    """Ищем таблицу с датами и PM2.5."""
    for table in driver.find_elements(By.TAG_NAME, "table"):
        text = table.get_attribute("textContent") or ""

        if "2026-10-" in text and "PM2.5" in text:
            return table

    return False


driver = webdriver.Firefox()
records = {}

try:
    driver.get(URL)

    # Ждём таблицу с историческими данными
    table = WebDriverWait(driver, 20).until(
        find_history_table
    )

    rows = table.find_elements(By.TAG_NAME, "tr")

    # 1. Ищем строку с датами
    header = max(
        (read_cells(row) for row in rows),
        key=lambda cells: sum(
            bool(re.search(r"2026-\d{2}-\d{2}", cell))
            for cell in cells
        )
    )

    # 2. Запоминаем номер столбца каждой даты
    date_columns = {}

    for index, value in enumerate(header):
        match = re.search(r"2026-\d{2}-\d{2}", value)

        if match:
            date = match.group()

            if date.startswith("2026-10-"):
                date_columns[index] = date

    print("Найдено дат октября:", len(date_columns))

    # 3. Извлекаем показатели
    for row in rows:
        cells = read_cells(row)

        if not cells:
            continue

        pollutant = clean_label(cells[0])

        if pollutant not in POLLUTANTS:
            continue

        column_name = POLLUTANTS[pollutant]

        for index, date in date_columns.items():
            if index >= len(cells):
                continue

            value = parse_number(cells[index])

            if date not in records:
                records[date] = {
                    "date": date,
                    "city": "Almaty",
                    "source": "Pollution Alert",
                    "data_type": "CAMS model"
                }

            records[date][column_name] = value

finally:
    driver.quit()


# 4. Создаём датасет
df = pd.DataFrame(records.values())

if df.empty:
    print("Данные за октябрь не найдены.")
    raise SystemExit

# 5. Проверяем значения
for col in POLLUTANTS.values():
    if col not in df.columns:
        df[col] = float("nan")

    df[col] = pd.to_numeric(df[col], errors="coerce")
    df.loc[df[col] < 0, col] = float("nan")

# Удаляем строки без обоих основных показателей
df = df.dropna(
    subset=["pm25_ug_m3", "pm10_ug_m3"],
    how="all"
)

# 6. Удаляем дубликаты
df = df.drop_duplicates(
    subset=["date", "city", "source"],
    keep="last"
)

df = df.sort_values("date")

# 7. Проверяем полноту месяца
all_dates = set(
    pd.date_range(
        "2026-10-01", "2026-10-31"
    ).strftime("%Y-%m-%d")
)

missing_dates = sorted(all_dates - set(df["date"]))

# 8. Сохраняем датасет
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

print("\nПАРСИНГ ЗАВЕРШЁН")
print("Записей:", len(df))
print("Дубликатов:", df.duplicated(
    subset=["date", "city", "source"]
).sum())
print("Отсутствующих дней:", len(missing_dates))
print("Пропущенные даты:", missing_dates)

print("\nПропуски по столбцам:")
print(df.isna().sum())

print("\nПервые строки:")
print(df.head().to_string(index=False))

print("\nСохранено:", OUTPUT)
