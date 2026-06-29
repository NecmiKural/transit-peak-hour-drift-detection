"""Salvador weather (Mar-May 2024) from the free Open-Meteo archive API.

No API key needed. Used to test whether peak boundaries shift on rainy days
(the lecturer's exact example: "on rainy days we need more buses").

Returns hourly precipitation; resample/forward-fill to 5-min to merge with
the boarding stream (align to TZ America/Bahia, UTC-3).
"""
from __future__ import annotations

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import requests

import config as C

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_hourly_precip(start=C.DATE_START, end=C.DATE_END):
    """Return a DataFrame [time, precip_mm, temp_c] for Salvador."""
    import pandas as pd

    params = {
        "latitude": C.LAT,
        "longitude": C.LON,
        "start_date": start,
        "end_date": end,
        "hourly": "precipitation,temperature_2m",
        "timezone": C.TZ,
    }
    r = requests.get(ARCHIVE_URL, params=params, timeout=30)
    r.raise_for_status()
    h = r.json()["hourly"]
    df = pd.DataFrame({
        "time": pd.to_datetime(h["time"]),
        "precip_mm": h["precipitation"],
        "temp_c": h["temperature_2m"],
    }).set_index("time")
    return df


if __name__ == "__main__":
    print(fetch_hourly_precip("2024-03-01", "2024-03-07").head())
