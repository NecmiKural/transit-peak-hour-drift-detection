"""Role D, boundary detection + drift analysis  [INTEGRATED].

Two complementary framings, both fed from the team's shared data layer:

  Framing 1, *signal-level* drift (data-driven peak boundaries)
      Stream each stop's boardings through an online adaptive-threshold peak
      detector (src/peaks.py) -> per-day morning/evening peak-start times ->
      CapyMOA ADWIN on that boundary series. Answers "where is the real peak
      and does the boundary move over time?". Independent of the model.

  Framing 2, *model-level* drift (classic concept drift)
      Watch Role C's online regressor error over time and flag where the error
      regime shifts (= concept drift the model must adapt to). Role C's
      prequential output is D's raw material here. Two variants:
        (a) windowed: run a change detector on C's per-day RMSE series
            (docs/role_C_modeling/role_c_windowed_metrics.csv), no Java needed;
        (b) per-instance: reuse C's ARF harness to get the per-instance error
            stream and feed ADWIN (see scripts/kaggle_drift_run.py; needs Java 17).

Data source: Role B's no-look-ahead feature table (features_stream.csv), the
same input Role C consumes, so D, C and B stay consistent.
"""
from __future__ import annotations

import sys as _sys
import pathlib as _pl

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import config as C
from src.peaks import OnlinePeakDetector
from src.drift import detect_boundary_drift
from src.features import load_feature_table

# Role C's windowed metrics (per-day MAE/RMSE per model per stop).
ROLE_C_WINDOWED = C.ROOT / "docs" / "role_C_modeling" / "role_c_windowed_metrics.csv"
ARF_MODEL = "capymoa_arf_10"

OFFICIAL = {"AM": 6 * 60, "PM": 17 * 60}


# =====================================================================
# Shared data access (Role B feature table)
# =====================================================================
def load_boardings(path=None) -> pd.DataFrame:
    """Return [timestamp, stop_id(str), boardings] from Role B's feature table."""
    df = load_feature_table(path) if path else load_feature_table()
    out = df[["timestamp", "stop_id", "boardings"]].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    out["stop_id"] = out["stop_id"].astype(str)
    return out


def day_flags(path=None) -> pd.DataFrame:
    """Per-date weekend / holiday / rain flags, derived from Role B's table.

    rain = that calendar day had daily precipitation > 1 mm.
    """
    df = load_feature_table(path) if path else load_feature_table()
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.normalize()
    agg = df.groupby("date").agg(
        is_holiday=("is_holiday", "max"),
        precip=("precipitation_mm", "max"),
    ).reset_index()
    agg["is_weekend"] = agg["date"].dt.dayofweek >= 5
    agg["is_rain"] = agg["precip"] > 1.0
    return agg[["date", "is_weekend", "is_holiday", "is_rain"]]


# =====================================================================
# Framing 1, data-driven peak boundaries + drift on the boundary series
# =====================================================================
def stop_boundaries(boardings: pd.DataFrame, stop_id: str) -> pd.DataFrame:
    """Run the online peak detector over one stop; return all AM/PM peak-start events."""
    sub = boardings[boardings["stop_id"] == str(stop_id)].sort_values("timestamp")
    det = OnlinePeakDetector()
    for ts, val in zip(sub["timestamp"], sub["boardings"]):
        det.update(ts, float(val))
    rows = [(e.date, e.period, e.start_minute) for e in det.events]
    return pd.DataFrame(rows, columns=["date", "period", "start_min"])


def boundaries_for_period(boardings, flags, stop_id: str, period: str) -> pd.DataFrame:
    """Per-day boundary-start (earliest in the window) for AM or PM, with flags."""
    ev = stop_boundaries(boardings, stop_id)
    ev = ev[ev["period"] == period]
    if ev.empty:
        return ev.assign(date=pd.to_datetime([]))
    out = ev.groupby("date", as_index=False)["start_min"].min()
    out["date"] = pd.to_datetime(out["date"])
    return out.merge(flags, on="date", how="left").sort_values("date").reset_index(drop=True)


def segment_summary(b: pd.DataFrame) -> dict:
    """Mean peak-start by weekday/weekend/holiday/rain + the actionable shifts."""
    def mean_where(mask) -> float:
        v = b.loc[mask, "start_min"]
        return float(v.mean()) if len(v) else float("nan")

    wk = (~b["is_weekend"]) & (~b["is_holiday"])
    res = {
        "n_days": int(len(b)),
        "weekday": mean_where(wk),
        "weekend": mean_where(b["is_weekend"]),
        "holiday": mean_where(b["is_holiday"]),
        "weekday_dry": mean_where(wk & (~b["is_rain"])),
        "weekday_rain": mean_where(wk & b["is_rain"]),
    }
    res["weekend_shift_min"] = res["weekend"] - res["weekday"]
    res["rain_shift_min"] = res["weekday_rain"] - res["weekday_dry"]
    return res


def boundary_drift(b: pd.DataFrame, allow_dev_fallback: bool = True):
    """ADWIN over the weekday peak-start series; returns (drift_dates, backend)."""
    wk = b[(~b["is_weekend"]) & (~b["is_holiday"])].sort_values("date")
    series = list(zip(wk["date"].dt.strftime("%Y-%m-%d"), wk["start_min"]))
    return detect_boundary_drift(series, kind="adwin", allow_dev_fallback=allow_dev_fallback)


# =====================================================================
# Framing 2, concept drift on Role C's online-model error
# =====================================================================
def load_role_c_rmse(stop_id: str, model: str = ARF_MODEL,
                     path=ROLE_C_WINDOWED) -> pd.DataFrame:
    """Role C's per-day RMSE series for one stop+model (the drift input)."""
    df = pd.read_csv(path)
    sub = df[(df["stop_id"].astype(str) == str(stop_id)) & (df["model"] == model)]
    return sub.sort_values("window_id")[["window_id", "n_instances", "MAE", "RMSE"]].reset_index(drop=True)


def concept_drift_from_windowed(stop_id: str, model: str = ARF_MODEL,
                                allow_dev_fallback: bool = True):
    """Run a change detector on Role C's ARF RMSE series.

    Returns (list of window_ids where drift fired, backend, rmse_series).
    This is Framing 2 with C's prequential output as D's raw material.
    """
    series_df = load_role_c_rmse(stop_id, model)
    pts = list(zip(series_df["window_id"].astype(str), series_df["RMSE"]))
    drifts, backend = detect_boundary_drift(pts, kind="adwin",
                                            allow_dev_fallback=allow_dev_fallback)
    drift_windows = [int(w) for w, _ in drifts]
    return drift_windows, backend, series_df


# =====================================================================
# helpers
# =====================================================================
def fmt(m: float) -> str:
    return "--:--" if (m != m) else "%02d:%02d" % (int(m) // 60, int(m) % 60)
