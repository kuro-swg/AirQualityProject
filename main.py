"""Единая точка запуска; по умолчанию анализ локальных данных."""
import argparse
from pathlib import Path
import runpy

BASE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description="Анализ воздуха и погоды Алматы")
    parser.add_argument("command", nargs="?", default="analyze", choices=["analyze", "check", "collect"])
    scripts = {"open-meteo": "open_meteo_parser.py", "aqicn": "selenium_parser.py",
               "cerns": "history_parser.py", "pollution-alert": "pollution_alert_parser.py",
               "weather-month": "weather_archive_parser.py", "weather-year": "weather_year_parser.py"}
    parser.add_argument("--source", choices=list(scripts))
    args = parser.parse_args()
    if args.command == "collect":
        if not args.source:
            parser.error("Для collect укажите --source")
        runpy.run_path(str(BASE / scripts[args.source]), run_name="__main__")
    else:
        from analysis import analyze, check_data
        if args.command == "check":
            print(check_data())
        else:
            analyze()

if __name__ == "__main__":
    main()
