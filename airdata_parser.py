
import re
from pathlib import Path
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select

URL = "https://airdata.kz/ru/"

driver = webdriver.Firefox()

try:
    driver.get(URL)

    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.TAG_NAME, "body")) > 0
    )

    # Даём динамическому календарю загрузиться
    time.sleep(3)

    print("Заголовок:", driver.title)

    # Исследуем выпадающие списки
    selects = driver.find_elements(By.TAG_NAME, "select")
    print("\nНайдено списков:", len(selects))

    for element in selects:
        dropdown = Select(element)
        options = [
            option.text.strip()
            for option in dropdown.options
        ]

        print("Варианты:", options[:30])

        # Выбираем Алматы, если он есть
        for option in options:
            if option.lower() in ("almaty", "алматы"):
                dropdown.select_by_visible_text(option)
                break

        if "2026" in options:
            dropdown.select_by_visible_text("2026")

    time.sleep(3)

    # Ищем элементы календаря с датами
    elements = driver.find_elements(
        By.CSS_SELECTOR,
        "[title], [aria-label], [data-date], time"
    )

    print("\nЭлементов с атрибутами:", len(elements))

    found = 0

    for element in elements:
        attributes = {
            "title": element.get_attribute("title"),
            "aria-label": element.get_attribute("aria-label"),
            "data-date": element.get_attribute("data-date"),
            "text": element.text.strip()
        }

        content = str(attributes)

        if re.search(r"2026-10|октя|october", content, re.I):
            print("\nНАЙДЕНА ДАТА:")
            print(attributes)
            print(element.get_attribute("outerHTML")[:500])
            found += 1

    print("\nНайдено подходящих элементов:", found)

    debug = Path(__file__).resolve().parent / "debug"
    debug.mkdir(exist_ok=True)
    driver.save_screenshot(str(debug / "airdata_debug.png"))

finally:
    driver.quit()
    