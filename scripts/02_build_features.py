"""Role B, build the streaming feature table (reproducible, repo-native).

Regenerates `data/processed/features_stream.csv` (the table Roles C/D consume)
from:
  * raw boarding CSV     -> data/raw/ (run scripts/01_download_data.py first)
  * weather              -> Open-Meteo archive (external/weather.py), cached
  * holidays             -> external/holidays_ssa.py

This is the repo-native version of `docs/role_B_external_features/role_b_features.py`
(the original Colab script). No Colab / Java needed.

Run:  python scripts/02_build_features.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from external.weather import fetch_hourly_precip  # noqa: E402
from external.holidays_ssa import holiday_dates  # noqa: E402
from src.features import build_feature_table, FEATURE_COLS  # noqa: E402

# Canonical (git-tracked) location: with Role B's deliverables under docs/.
ROLE_B_DIR = C.ROOT / "docs" / "role_B_external_features"
WEATHER_CACHE = ROLE_B_DIR / "weather_salvador.csv"
OUT = ROLE_B_DIR / "features_stream.csv"


def get_weather() -> pd.DataFrame:
    """Hourly Salvador weather as [precipitation_mm, temperature_2m], cached."""
    if WEATHER_CACHE.exists():
        print(f"  weather: cache {WEATHER_CACHE}")
        return pd.read_csv(WEATHER_CACHE, parse_dates=["timestamp"]).set_index("timestamp")
    print("  weather: fetching from Open-Meteo ...")
    w = fetch_hourly_precip(C.DATE_START, C.DATE_END)  # index 'time', precip_mm/temp_c
    w = w.rename(columns={"precip_mm": "precipitation_mm", "temp_c": "temperature_2m"})
    w.index.name = "timestamp"
    w.to_csv(WEATHER_CACHE)
    return w


def main():
    boarding_csv = C.DATA_RAW / C.HF_FILES["boarding"]
    if not boarding_csv.exists():
        raise FileNotFoundError(
            f"{boarding_csv} missing, run `python scripts/01_download_data.py` first."
        )

    weather = get_weather()
    holidays = holiday_dates(2024)
    print(f"  holidays in window: {sorted(holidays)}")

    df = build_feature_table(boarding_csv, weather, holidays)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"\n  saved {OUT}  ({OUT.stat().st_size / 1e6:.1f} MB)")
    print(f"  shape: {df.shape}")
    print(f"  day_type:\n{df['day_type'].value_counts().to_string()}")
    print(f"  model feature columns ({len(FEATURE_COLS)}): {FEATURE_COLS}")
    missing = df.isnull().sum()
    print("  missing:", "none" if not missing.any() else missing[missing > 0].to_dict())


if __name__ == "__main__":
    main()
