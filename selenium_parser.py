
import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://aqicn.org/city/almaty/"
FILE = Path(__file__).resolve().parent / "data" / "aqicn_observations.csv"

# Какие показатели разрешаем собирать
POLLUTANTS = {
    "PM2.5 AQI",
    "PM10 AQI",
    "NO2 AQI",
    "CO AQI",
    "SO2 AQI",
    "O3 AQI"
}

def parse_number(value):
    try:
        return float(value.strip())
    except ValueError:
        return None

driver = webdriver.Firefox()

try:
    driver.get(URL)

    # Ждём появления таблицы с числовыми данными
    WebDriverWait(driver, 20).until(
        lambda d: any(
            "NO2 AQI" in row.text or "CO AQI" in row.text
            for row in d.find_elements(By.TAG_NAME, "tr")
        )
    )

    rows = driver.find_elements(By.TAG_NAME, "tr")

    collected_at = datetime.now(
        ZoneInfo("Asia/Almaty")
    ).isoformat(timespec="seconds")

    results = []

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        values = [cell.text.strip() for cell in cells]

        if len(values) < 5:
            continue

        pollutant = values[0]

        if pollutant not in POLLUTANTS:
            continue

        current = parse_number(values[1])

        if current is None:
            continue

        results.append({
            "collected_at": collected_at,
            "station": "Almaty US Embassy",
            "pollutant": pollutant,
            "aqi": current,
            "min_aqi": parse_number(values[3]),
            "max_aqi": parse_number(values[4])
        })

    if results:
        FILE.parent.mkdir(exist_ok=True)

        file_exists = FILE.exists() and FILE.stat().st_size > 0

        if file_exists:
            with FILE.open(encoding="utf-8-sig", newline="") as existing:
                if next(csv.reader(existing), []) != list(results[0].keys()):
                    raise ValueError("Несовместимая структура CSV AQICN")

        with FILE.open(
            "a", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file, fieldnames=results[0].keys()
            )

            if not file_exists:
                writer.writeheader()

            writer.writerows(results)

        print("Данные сохранены!")
        print("Количество записей:", len(results))

        for item in results:
            print(item)
    else:
        print("Числовые показатели не найдены.")

finally:
    driver.quit()
