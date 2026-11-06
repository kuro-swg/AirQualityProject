
import re
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

URL = (
    "https://www.pogodaiklimat.ru/monitor.php"
    "?id=36870&month=10&year=2026"
)

OUTPUT = (
    Path(__file__).resolve().parent
    / "data"
    / "almaty_weather_october_2026.csv"
)


def parse_number(text):
    """Преобразует текст ячейки в число."""
    text = text.strip().replace(",", ".")
    text = text.replace("−", "-")

    try:
        return float(text)
    except ValueError:
        return None


def extract_weather(driver):
    """Находит таблицу с суточными наблюдениями."""
    best_result = []

    tables = driver.find_elements(By.TAG_NAME, "table")

    print("Всего HTML-таблиц:", len(tables))

    for table in tables:
        records = {}

        for row in table.find_elements(By.TAG_NAME, "tr"):
            cells = row.find_elements(By.XPATH, "./td")
            values = [cell.text.strip() for cell in cells]

            # Ожидаем 6 ячеек в строке
            if len(values) != 6:
                continue

            # Первая ячейка — день месяца
            if not re.fullmatch(r"\d{1,2}", values[0]):
                continue

            day = int(values[0])

            if not 1 <= day <= 31:
                continue

            numbers = [parse_number(v) for v in values[1:]]

            # Исключаем строки без температурных данных
            if any(n is None for n in numbers[:3]):
                continue

            records[day] = {
                "date": f"2026-10-{day:02d}",
                "city": "Almaty",
                "temp_min_c": numbers[0],
                "temp_mean_c": numbers[1],
                "temp_max_c": numbers[2],
                "temp_anomaly_c": numbers[3],
                "precipitation_mm": numbers[4],
                "source": "Pogoda i Klimat"
            }

        if len(records) > len(best_result):
            best_result = list(records.values())

    return best_result


driver = webdriver.Firefox()

try:
    driver.get(URL)

    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.TAG_NAME, "table")) > 0
    )

    results = extract_weather(driver)

finally:
    driver.quit()


if not results:
    print("Таблица с погодными данными не найдена.")
    raise SystemExit

# Создаём датасет
df = pd.DataFrame(results)

# Удаляем возможные дубликаты
df = df.drop_duplicates(
    subset=["date", "city", "source"],
    keep="last"
)

# Удаляем некорректные осадки
df.loc[
    df["precipitation_mm"] < 0,
    "precipitation_mm"
] = float("nan")

# Проверяем температуры
invalid_temp = df[
    (df["temp_min_c"] > df["temp_mean_c"])
    | (df["temp_mean_c"] > df["temp_max_c"])
]

# Сортируем даты
df = df.sort_values("date")

# Проверяем полноту октября
all_dates = set(
    pd.date_range(
        "2026-10-01", "2026-10-31"
    ).strftime("%Y-%m-%d")
)

missing = sorted(all_dates - set(df["date"]))

# Сохраняем
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(
    OUTPUT,
    index=False,
    encoding="utf-8-sig"
)

print("\nПАРСИНГ ЗАВЕРШЁН")
print("Количество записей:", len(df))
print("Дубликатов:", df.duplicated(
    subset=["date", "city", "source"]
).sum())

print("Пропущенные даты:", missing)
print("Некорректных температурных строк:", len(invalid_temp))

print("\nПропущенные значения:")
print(df.isna().sum())

print("\nПервые пять строк:")
print(df.head().to_string(index=False))

print("\nФайл:", OUTPUT)
