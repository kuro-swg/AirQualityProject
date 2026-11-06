"""Проверка локальных данных, объединение по датам и воспроизводимый отчёт."""
from pathlib import Path
import csv

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
REPORTS = BASE / "reports"
PLOTS = BASE / "plots"
# Периоды исследования сохранены явно; даты строк никогда не заменяются.
AIR_START, AIR_END = "2026-10-01", "2026-10-31"
WEATHER_START, WEATHER_END = "2025-11-01", "2026-10-31"


def check_data():
    lines = ["# Качество данных", ""]
    for path in sorted(DATA.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.reader(stream))
        if not records:
            lines.append(f"- {path.name}: пустой файл")
            continue
        if any(len(row) != len(records[0]) for row in records[1:]):
            raise ValueError(f"{path.name}: строки не соответствуют заголовку")
        df = pd.read_csv(path)
        date_col = next((c for c in ["date", "time", "collected_at"] if c in df), None)
        keys = [c for c in [date_col, "city", "source", "station", "pollutant"] if c in df]
        duplicates = int(df.duplicated(keys).sum()) if keys else int(df.duplicated().sum())
        numeric = df.select_dtypes("number")
        nonnegative = [c for c in numeric if c in {"aqi", "aqi_min", "aqi_max", "min_aqi", "max_aqi", "pm2_5", "pm10", "precipitation_mm", "hours", "stations"} or c.endswith("_ug_m3")]
        negative = int((df[nonnegative] < 0).sum().sum())
        lines.append(f"- {path.name}: {len(df)} строк; пропусков значений: {int(df.isna().sum().sum())}; дубликатов: {duplicates}; отрицательных концентраций/индексов/осадков: {negative}.")
        if date_col:
            dates = pd.to_datetime(df[date_col].str[:10], errors="coerce")
            lines.append(f"  Даты: {dates.min()} — {dates.max()}; некорректных: {int(dates.isna().sum())}.")
            period = ((WEATHER_START, WEATHER_END) if path.name == "almaty_weather_year.csv"
                      else (AIR_START, AIR_END) if "october_2026" in path.name else None)
            if period:
                missing = pd.date_range(*period).difference(pd.DatetimeIndex(dates.dropna()))
                lines.append("  Пропущенные дни периода: " + (", ".join(missing.strftime("%Y-%m-%d")) or "нет") + ".")
        if {"temp_min_c", "temp_mean_c", "temp_max_c"} <= set(df):
            invalid = (df.temp_min_c > df.temp_mean_c) | (df.temp_mean_c > df.temp_max_c)
            lines.append(f"  Нарушений порядка температур: {int(invalid.sum())}.")
        if "hours" in df:
            lines.append(f"  Полных суток: {int(df.hours.eq(24).sum())}; некорректных заполненных часов: {int((df.hours.notna() & ~df.hours.between(1, 24)).sum())}.")
    REPORTS.mkdir(exist_ok=True)
    report = "\n".join(lines) + "\n"
    (REPORTS / "data_quality.md").write_text(report, encoding="utf-8")
    return report


def analyze():
    check_data()
    PLOTS.mkdir(exist_ok=True)
    air = pd.read_csv(DATA / "almaty_october_2026.csv", parse_dates=["date"])
    weather = pd.read_csv(DATA / "almaty_weather_year.csv", parse_dates=["date"])
    for name, frame in [("воздух", air), ("погода", weather)]:
        if frame.duplicated(["date", "city"]).any():
            raise ValueError(f"Неоднозначные наблюдения по дате и городу: {name}")
    # Календарная сетка сохраняет пропуски для будущей работы с временными рядами.
    calendar = pd.DataFrame({"date": pd.date_range(AIR_START, AIR_END), "city": "Almaty"})
    merged = calendar.merge(air, on=["date", "city"], how="left", validate="one_to_one")
    merged = merged.merge(weather, on=["date", "city"], how="left",
                          suffixes=("_air", "_weather"), validate="one_to_one")
    merged["air_day_complete"] = merged["hours"].eq(24)
    merged.to_csv(DATA / "daily_analysis.csv", index=False, encoding="utf-8-sig")
    full = merged[merged.air_day_complete].copy()
    if full.empty:
        raise ValueError("Нет полных суток загрязнения для анализа")
    columns = ["pm25_ug_m3", "pm10_ug_m3", "aqi", "temp_mean_c", "precipitation_mm"]
    full[columns].describe().to_csv(REPORTS / "statistics.csv", encoding="utf-8-sig")
    correlation_rows = []
    for pollutant in columns[:3]:
        for factor in columns[3:]:
            pairs = full[[pollutant, factor]].dropna()
            r = pairs[pollutant].corr(pairs[factor]) if len(pairs) >= 3 and (pairs.nunique() > 1).all() else float("nan")
            correlation_rows.append({"pollutant": pollutant, "weather_factor": factor, "n": len(pairs), "pearson_r": r})
    pd.DataFrame(correlation_rows).to_csv(REPORTS / "correlations.csv", index=False, encoding="utf-8-sig")

    # Пропуски и неполные дни разрывают линию, а не соединяются через отсутствующие даты.
    daily = merged.set_index("date")
    clean_air = daily[["pm25_ug_m3", "pm10_ug_m3", "aqi"]].where(daily.air_day_complete, axis=0)
    for names, title, ylabel, filename in [
        (["pm25_ug_m3", "pm10_ug_m3"], "Загрязнение воздуха в Алматы — октябрь 2026", "мкг/м³", "pm25_pm10_line.png"),
        (["aqi"], "AQI в Алматы — октябрь 2026 (CERNS)", "AQI", "aqi_line.png"),
        (["temp_mean_c"], "Температура в Алматы — октябрь 2026", "°C", "temperature_line.png")]:
        frame = daily if names == ["temp_mean_c"] else clean_air
        ax = frame[names].plot(figsize=(10, 5), marker="o", title=title)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Дата")
        ax.grid(alpha=.3)
        ax.figure.tight_layout()
        ax.figure.savefig(PLOTS / filename, dpi=150)
        plt.close(ax.figure)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, factor, label in zip(axes, columns[3:], ["Температура, °C", "Осадки, мм"]):
        ax.scatter(full[factor], full.pm25_ug_m3)
        ax.set(xlabel=label, ylabel="PM2.5, мкг/м³", title=f"Полные сутки: n={len(full[[factor, 'pm25_ug_m3']].dropna())}")
        ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(PLOTS / "pm25_vs_weather.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    weather.set_index("date").temp_mean_c.plot(ax=axes[0], title="Температура в Алматы за год", ylabel="°C")
    rain = weather.set_index("date").precipitation_mm.resample("MS").sum(min_count=1)
    axes[1].bar(rain.index, rain.values, width=20)
    axes[1].set(title="Осадки по месяцам", ylabel="мм")
    clean_air[["pm25_ug_m3", "pm10_ug_m3"]].plot(ax=axes[2], title="Загрязнение — октябрь 2026 (полные сутки)", ylabel="мкг/м³")
    fig.tight_layout()
    fig.savefig(PLOTS / "almaty_analysis.png", dpi=150)
    plt.close(fig)

    peak = full.loc[full.pm25_ug_m3.idxmax()]
    report = ["# Анализ погоды и загрязнения воздуха в Алматы", "",
              f"Период анализа: {AIR_START} — {AIR_END}. Погодный архив: {WEATHER_START} — {WEATHER_END}.",
              f"Наблюдений загрязнения: {len(air)}; полных суток для анализа: {len(full)} из {len(merged)}.",
              f"Среднее PM2.5 по доступным полным суткам: {full.pm25_ug_m3.mean():.2f} мкг/м³; медиана: {full.pm25_ug_m3.median():.2f}.",
              f"Максимум PM2.5: {peak.pm25_ug_m3:.2f} мкг/м³ ({peak.date:%Y-%m-%d}).", "",
              "## Связь с погодой (коэффициент Пирсона)", ""]
    for row in correlation_rows:
        value = (f"r={row['pearson_r']:.3f}" if pd.notna(row['pearson_r'])
                 else "не определена: недостаточно пар или один из показателей не меняется")
        report.append(f"- {row['pollutant']} / {row['weather_factor']}: {value}, n={row['n']}.")
    report.extend(["", "Выборка мала и покрывает часть октября. Результаты предварительные; корреляция не доказывает причинную связь. Пропуски не заполнялись, неполные сутки исключены из статистики. AQI и концентрации не смешиваются; источники сохранены в таблице.",
                   "", "Таблица daily_analysis.csv сохраняет каждую дату октября, отсутствующие наблюдения и флаг полноты суток. Она не содержит прогнозов. Для прогнозирования нужно расширить историю и проверять модель на более поздних датах без перемешивания временного ряда.", ""])
    (REPORTS / "summary.md").write_text("\n".join(report), encoding="utf-8")
    check_data()
    print("Готово: data/daily_analysis.csv, reports/ и plots/")


if __name__ == "__main__":
    analyze()
