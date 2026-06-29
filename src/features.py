"""Streaming feature construction (Role B, external data & features).

Two entry points:

1. Batch feature table (offline preprocessing, what Role B ships):
   `build_feature_table(...)` reproduces `data/processed/features_stream.csv`
   from the raw boarding CSV + weather + holidays. All lag/rolling features
   use `.shift(1)` first, so there is **no look-ahead**, the table is safe to
   replay as a stream for prequential evaluation.

2. Online path: the `StreamingFeatures` class builds the same features one
   interval at a time from fixed-size buffers (for a pure-streaming model).

Downstream (Roles C/D) normally just call `load_feature_table()` and then
`iter_feature_rows(df, stop_id)`.
"""
from __future__ import annotations

import sys as _sys
import pathlib as _pl
from collections import deque

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

# ---- feature definitions (kept identical to Role B's features_stream.csv) ----
LAG_STEPS = [1, 2, 3, 6, 12]
ROLLING_WINDOWS = [6, 12]

# Columns a streaming model consumes (excludes target/ids/string labels).
FEATURE_COLS = [
    "hour_of_day", "sin_hour", "cos_hour", "day_of_week",
    "is_weekend", "is_holiday",
    "boarding_lag_1", "boarding_lag_2", "boarding_lag_3",
    "boarding_lag_6", "boarding_lag_12",
    "rolling_mean_6", "rolling_std_6", "rolling_mean_12", "rolling_std_12",
    "precipitation_mm", "temperature_2m", "is_raining",
]
TARGET_COL = "boardings"
# Canonical, git-tracked feature table lives with Role B's deliverables.
DEFAULT_FEATURE_TABLE = C.ROOT / "docs" / "role_B_external_features" / "features_stream.csv"


# ----------------------------------------------------------------- batch build
def load_boarding_long(boarding_csv):
    """Read the wide raw boarding CSV (timestamp x stop) and melt to long."""
    import pandas as pd

    wide = pd.read_csv(boarding_csv, parse_dates=[0], index_col=0)
    wide.index.name = "timestamp"
    long = wide.reset_index().melt(
        id_vars="timestamp", var_name="stop_id", value_name="boardings"
    )
    long["boardings"] = pd.to_numeric(long["boardings"], errors="coerce").fillna(0.0)
    return long.sort_values(["stop_id", "timestamp"]).reset_index(drop=True)


def merge_external(boarding_long, weather_hourly, holiday_set):
    """Join hourly weather (forward-filled to 5 min) and holiday flags.

    weather_hourly: DataFrame indexed by hourly timestamp with columns
        'precipitation_mm', 'temperature_2m' (tz-naive, Salvador local time).
    holiday_set: set of 'YYYY-MM-DD' strings.
    """
    import pandas as pd

    df = boarding_long.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if df["timestamp"].dt.tz is not None:
        df["timestamp"] = df["timestamp"].dt.tz_convert(C.TZ).dt.tz_localize(None)

    w = weather_hourly.copy()
    w.index = pd.to_datetime(w.index)
    if w.index.tz is not None:
        w.index = w.index.tz_localize(None)

    df["hour_ts"] = df["timestamp"].dt.floor("h")
    w.index.name = "hour_ts"
    df = df.merge(w.reset_index(), on="hour_ts", how="left")
    df[["precipitation_mm", "temperature_2m"]] = df[
        ["precipitation_mm", "temperature_2m"]
    ].ffill()
    df = df.drop(columns=["hour_ts"])

    dstr = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["is_holiday"] = dstr.isin(holiday_set)
    return df


def _add_features_one_stop(grp):
    import numpy as np

    grp = grp.sort_values("timestamp").copy()
    ts = grp["timestamp"]
    grp["hour_of_day"] = ts.dt.hour + ts.dt.minute / 60.0
    grp["minute_of_hour"] = ts.dt.minute
    grp["sin_hour"] = np.sin(2 * np.pi * ts.dt.hour / 24)
    grp["cos_hour"] = np.cos(2 * np.pi * ts.dt.hour / 24)
    grp["day_of_week"] = ts.dt.dayofweek
    grp["is_weekend"] = grp["day_of_week"] >= 5
    grp["week_of_year"] = ts.dt.isocalendar().week.astype(int)
    grp["day_type"] = np.where(
        grp["is_holiday"], "holiday",
        np.where(grp["is_weekend"], "weekend", "weekday"),
    )
    for k in LAG_STEPS:
        grp[f"boarding_lag_{k}"] = grp["boardings"].shift(k)
    for w in ROLLING_WINDOWS:
        shifted = grp["boardings"].shift(1)  # shift first → no look-ahead
        grp[f"rolling_mean_{w}"] = shifted.rolling(w, min_periods=1).mean()
        grp[f"rolling_std_{w}"] = shifted.rolling(w, min_periods=1).std().fillna(0)
    grp["is_raining"] = grp["precipitation_mm"] > 0.1
    import numpy as _np
    grp["rain_intensity"] = __import__("pandas").cut(
        grp["precipitation_mm"],
        bins=[-_np.inf, 0.1, 2.5, 7.6, _np.inf],
        labels=["none", "light", "moderate", "heavy"],
    )
    return grp


def build_features(merged):
    """Add calendar/cyclic/lag/rolling/rain features per stop (no look-ahead)."""
    import pandas as pd

    parts = [_add_features_one_stop(g) for _, g in merged.groupby("stop_id", sort=False)]
    df = pd.concat(parts, ignore_index=True).sort_values(
        ["timestamp", "stop_id"]
    ).reset_index(drop=True)
    fill = [c for c in df.columns if c.startswith(("boarding_lag_", "rolling_"))]
    df[fill] = df[fill].fillna(0.0)
    return df


def build_feature_table(boarding_csv, weather_hourly, holiday_set):
    """Full Role B pipeline: raw boarding + weather + holidays -> feature table."""
    long = load_boarding_long(boarding_csv)
    merged = merge_external(long, weather_hourly, holiday_set)
    return build_features(merged)


# --------------------------------------------------------------- consumer API
def load_feature_table(path=DEFAULT_FEATURE_TABLE):
    """Load the ready-made feature table for Roles C/D."""
    import pandas as pd

    return pd.read_csv(
        path, parse_dates=["timestamp"],
        dtype={"holiday_name": "string"}, low_memory=False,
    )


def iter_feature_rows(df, stop_id, feature_cols=None):
    """Yield (timestamp, x_dict, y) in time order for one stop, prequential entry point.

    Accepts stop_id as int or str (the CSV stores it as int64).
    """
    feature_cols = feature_cols or FEATURE_COLS
    sub = df[df["stop_id"].astype(str) == str(stop_id)].sort_values("timestamp")
    for _, row in sub.iterrows():
        x = {c: float(row[c]) for c in feature_cols}
        yield row["timestamp"], x, float(row[TARGET_COL])


# --------------------------------------------------------------- online path
class StreamingFeatures:
    """Build the same features one interval at a time (pure-streaming model)."""

    def __init__(self, intervals_per_day: int = 288):
        self.prev: deque[float] = deque(maxlen=intervals_per_day + 2)

    def transform(self, ts, value: float, holiday: int = 0,
                  rain_mm: float = 0.0) -> dict:
        recent = list(self.prev)
        feats = {
            "minute_of_day": ts.hour * 60 + ts.minute,
            "dow": ts.dayofweek,
            "is_weekend": int(ts.dayofweek >= 5),
            "lag_1": recent[-1] if len(recent) >= 1 else 0.0,
            "lag_2": recent[-2] if len(recent) >= 2 else 0.0,
            "lag_daybefore": recent[0] if len(recent) == self.prev.maxlen else 0.0,
            "roll_mean_6": (sum(recent[-6:]) / min(6, len(recent))) if recent else 0.0,
            "is_holiday": holiday,
            "rain_mm": rain_mm,
            "is_rain": int(rain_mm > 0.1),
        }
        self.prev.append(value)
        return feats


if __name__ == "__main__":
    df = load_feature_table()
    print("feature table:", df.shape)
    print("columns:", list(df.columns))
    ts, x, y = next(iter_feature_rows(df, C.START_SUBSET[1]))
    print("first row for", C.START_SUBSET[1], "->", ts, "y=", y, "| x has", len(x), "features")
