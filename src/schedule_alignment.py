"""Role D - Framing 3: scheduled-service vs realized-demand alignment.

Idea (Role F's suggestion, built into Role D):
    The two earlier framings look at the *demand* signal alone (when the
    boarding peak is, and whether that boundary drifts). This adds the
    *supply* side: from the GTFS timetable (`stop_times.txt`) we build, per
    stop, a scheduled bus-arrival profile, find where scheduled service is
    concentrated, and compare that to where demand actually peaks. The gap
    (minutes) is the actionable number: "buses are scheduled to peak at HH:MM
    but riders peak at HH:MM -> shift the service window".

This separates two distinct things:
  * schedule (mis)alignment  = scheduled-arrival peak  vs  boarding peak
    (how well the timetable matches demand - a planning decision);
  * concept drift in demand  = Framings 1 & 2 (weather/holiday effects).

IMPORTANT - what is and isn't "online":
  `stop_times.txt` is a *static* timetable, so this alignment comparison is a
  descriptive supply-vs-demand layer, NOT an online-ML task. It sits on top of
  the streaming detection (Framings 1 & 2 keep satisfying the streaming
  requirement). It is also *scheduled* arrivals, not realized ones - actual
  vehicle arrivals (AVL) are not in the 10-stop subset - so we phrase findings
  as "scheduled service vs demand".

The scheduled peak is extracted with the *same rule* as the online demand
detector (mean + K*std sustained inside the morning/evening window, see
src/peaks.py), applied to the static profile, so the two boundaries are
comparable.
"""
from __future__ import annotations

import sys as _sys
import pathlib as _pl

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import config as C
from src.drift_analysis import (
    load_boardings, day_flags, boundaries_for_period, segment_summary, OFFICIAL, fmt,
)

# GTFS files needed for the timetable -> arrival profile.
GTFS_DIR = C.DATA_RAW / "gtfs"
GTFS_FILES = ("stop_times.txt", "trips.txt", "calendar.txt")

BINS_PER_DAY = 24 * 60 // 5  # 288 five-minute bins
DAYTYPE_FLAG = {"weekday": "tuesday", "weekend": "saturday", "sunday": "sunday"}


# =====================================================================
# GTFS loading
# =====================================================================
def ensure_gtfs(repo_id: str = C.HF_REPO_5MIN) -> None:
    """Download the three GTFS files we need into data/raw/gtfs/ if missing."""
    GTFS_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in GTFS_FILES if not (GTFS_DIR / f).exists()]
    if not missing:
        return
    from huggingface_hub import hf_hub_download

    for fname in missing:
        hf_hub_download(
            repo_id=repo_id, filename=f"gtfs/{fname}", repo_type="dataset",
            local_dir=str(C.DATA_RAW),
        )


def _arrival_to_minute(value: str) -> float:
    """GTFS HH:MM:SS -> minute-of-day in [0,1440). Handles times >= 24:00:00."""
    try:
        h, m, _s = str(value).strip().split(":")
        return (int(h) * 60 + int(m)) % 1440
    except (ValueError, AttributeError):
        return float("nan")


def load_stop_times(stops: list[str], gtfs_dir: _pl.Path = GTFS_DIR,
                    chunksize: int = 500_000) -> pd.DataFrame:
    """Read stop_times.txt in chunks, keep only our stops, return
    [trip_id, stop_id, arr_min]. Memory stays modest despite the ~88 MB file."""
    stops = set(map(str, stops))
    path = gtfs_dir / "stop_times.txt"
    keep = []
    for chunk in pd.read_csv(
        path, usecols=["trip_id", "arrival_time", "stop_id"],
        dtype={"trip_id": str, "stop_id": str, "arrival_time": str},
        chunksize=chunksize,
    ):
        sub = chunk[chunk["stop_id"].isin(stops)]
        if not sub.empty:
            keep.append(sub)
    if not keep:
        return pd.DataFrame(columns=["trip_id", "stop_id", "arr_min"])
    df = pd.concat(keep, ignore_index=True)
    df["arr_min"] = df["arrival_time"].map(_arrival_to_minute)
    return df.dropna(subset=["arr_min"])[["trip_id", "stop_id", "arr_min"]]


def trip_daytypes(gtfs_dir: _pl.Path = GTFS_DIR) -> dict[str, dict[str, bool]]:
    """Map trip_id -> {'weekday':bool,'weekend':bool,'sunday':bool} via
    trips.txt (trip->service) and calendar.txt (service day-of-week flags)."""
    trips = pd.read_csv(gtfs_dir / "trips.txt",
                        usecols=["trip_id", "service_id"],
                        dtype={"trip_id": str, "service_id": str})
    cal = pd.read_csv(gtfs_dir / "calendar.txt", dtype={"service_id": str})

    svc = {}
    for _, r in cal.iterrows():
        svc[str(r["service_id"])] = {
            dt: bool(int(r[flag])) for dt, flag in DAYTYPE_FLAG.items()
        }
    default = {dt: False for dt in DAYTYPE_FLAG}
    return {
        str(r.trip_id): svc.get(str(r.service_id), default)
        for r in trips.itertuples(index=False)
    }


# =====================================================================
# Scheduled arrival profile + peak extraction
# =====================================================================
def scheduled_profile(stop_times: pd.DataFrame, trip_dt: dict,
                      stop_id: str, day_type: str) -> np.ndarray:
    """Count scheduled arrivals per 5-min bin at one stop on a representative
    day of `day_type` ('weekday'|'weekend'|'sunday'). Returns array[288]."""
    sub = stop_times[stop_times["stop_id"] == str(stop_id)]
    prof = np.zeros(BINS_PER_DAY)
    for trip_id, arr_min in zip(sub["trip_id"], sub["arr_min"]):
        if trip_dt.get(trip_id, {}).get(day_type, False):
            prof[int(arr_min) // 5] += 1.0
    return prof


def scheduled_peak_start(profile: np.ndarray, period: str,
                         k: float | None = None,
                         min_sustain: int | None = None) -> float:
    """Minute-of-day where scheduled service starts peaking in the AM/PM window.

    Mirrors the online demand detector's rule (peaks.py): a bin is 'high' when
    arrivals exceed day mean + K*std; the first run of `min_sustain` high bins
    inside the window marks the scheduled peak start.
    """
    k = C.SCHED_THRESH_K if k is None else k
    min_sustain = C.SCHED_MIN_SUSTAIN if min_sustain is None else min_sustain
    smooth = getattr(C, "SCHED_SMOOTH_BINS", 1)
    if profile.sum() == 0:
        return float("nan")

    # light smoothing so steady-headway schedules still reveal their busiest ramp
    if smooth and smooth > 1:
        prof = np.convolve(profile, np.ones(smooth) / smooth, mode="same")
    else:
        prof = profile
    thr = prof.mean() + k * prof.std()
    lo, hi = C.AM_WINDOW if period == "AM" else C.PM_WINDOW
    lo_b, hi_b = lo // 5, hi // 5

    run = 0
    for b in range(lo_b, min(hi_b + 1, BINS_PER_DAY)):
        if prof[b] > thr:
            run += 1
            if run >= min_sustain:
                return float((b - (min_sustain - 1)) * 5)
        else:
            run = 0
    return float("nan")


# =====================================================================
# Alignment: scheduled peak vs demand peak
# =====================================================================
def alignment_table(stops: dict | None = None, st=None, trip_dt=None,
                    boardings=None, flags=None) -> pd.DataFrame:
    """For each stop x period x day-type: scheduled peak-start vs demand
    peak-start, and the gap (demand - scheduled) in minutes.

    Positive gap  => demand peaks LATER than service is concentrated
                     (consider shifting the service window later).
    Negative gap  => service is concentrated later than demand peaks.

    The four data inputs can be passed in (to avoid re-reading the ~88 MB
    stop_times.txt when a caller also needs them, e.g. for plotting).
    """
    stops = stops or C.STOPS
    if st is None:
        ensure_gtfs()
        st = load_stop_times(list(stops.keys()))
    if trip_dt is None:
        trip_dt = trip_daytypes()
    if boardings is None:
        boardings = load_boardings()
    if flags is None:
        flags = day_flags()

    rows: list[dict] = []
    for stop_id, meta in stops.items():
        label = meta[0] if isinstance(meta, (tuple, list)) else str(meta)
        for period in ("AM", "PM"):
            b = boundaries_for_period(boardings, flags, stop_id, period)
            demand = segment_summary(b) if not b.empty else {}
            for day_type, demand_key in (("weekday", "weekday"), ("weekend", "weekend")):
                prof = scheduled_profile(st, trip_dt, stop_id, day_type)
                sched = scheduled_peak_start(prof, period)
                dem = demand.get(demand_key, float("nan"))
                gap = dem - sched if (sched == sched and dem == dem) else float("nan")
                rows.append({
                    "stop": stop_id, "label": label, "period": period,
                    "day_type": day_type,
                    "scheduled_peak": fmt(sched), "demand_peak": fmt(dem),
                    "official": fmt(OFFICIAL[period]),
                    "gap_min": round(gap, 1) if gap == gap else float("nan"),
                    "n_sched_arrivals": int(prof.sum()),
                    "recommendation": _recommend(gap),
                })
    return pd.DataFrame(rows)


def _recommend(gap_min: float, tol: float = 15.0) -> str:
    """Plain-language, operator-facing recommendation from the gap."""
    if gap_min != gap_min:  # NaN
        return "insufficient data"
    if abs(gap_min) <= tol:
        return "aligned (within 15 min)"
    if gap_min > 0:
        return f"demand peaks ~{abs(gap_min):.0f} min later -> shift service window later"
    return f"demand peaks ~{abs(gap_min):.0f} min earlier -> shift service window earlier"


if __name__ == "__main__":
    df = alignment_table()
    cols = ["stop", "label", "period", "day_type", "scheduled_peak",
            "demand_peak", "gap_min", "recommendation"]
    print(df[cols].to_string(index=False))
