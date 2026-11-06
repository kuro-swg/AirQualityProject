"""Почасовые концентрации Open-Meteo, отдельно от индексов AQI."""
from pathlib import Path
import pandas as pd
import requests

OUTPUT = Path(__file__).resolve().parent / "data" / "open_meteo_hourly.csv"

def main():
    response = requests.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={"latitude": 43.2389, "longitude": 76.8897,
                "hourly": "pm2_5,pm10", "past_days": 1, "forecast_days": 0,
                "timezone": "Asia/Almaty"}, timeout=30)
    response.raise_for_status()
    df = pd.DataFrame(response.json()["hourly"])
    df["city"] = "Almaty"
    df["source"] = "Open-Meteo"
    df = df.dropna(subset=["pm2_5", "pm10"], how="all")
    if OUTPUT.exists():
        old = pd.read_csv(OUTPUT)
        if set(old.columns) != set(df.columns):
            raise ValueError("Несовместимая структура CSV Open-Meteo")
        df = pd.concat([old, df], ignore_index=True)
    df = df.drop_duplicates(["time", "city", "source"], keep="last").sort_values("time")
    OUTPUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print("Сохранено наблюдений:", len(df), OUTPUT)

if __name__ == "__main__":
    main()
