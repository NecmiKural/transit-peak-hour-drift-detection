"""Role D end-to-end, runs both drift framings on the team's shared data.

Inputs (already in the repo, git-tracked):
  - Role B: docs/role_B_external_features/features_stream.csv  (boardings + flags)
  - Role C: docs/role_C_modeling/role_c_windowed_metrics.csv   (ARF per-day RMSE)

Outputs (outputs/, tracked):
  - boundary_points_real.csv        Framing 1: per-day AM/PM peak-start points
                                    (RELIABLE stops only; see the reliability gate)
  - ampm_summary_real.csv           Framing 1: per-stop/period segment summary
                                    (all stops, each flagged reliable / not)
  - role_d_concept_drift_offline.csv  Framing 2 (offline DEV detector). The
                                    canonical CapyMOA-ADWIN result lives in
                                    role_d_concept_drift.csv (Kaggle run) and is
                                    NOT overwritten here.

Then: python scripts/plot_boundaries.py  to (re)draw figures/ampm_<stop>.png

Runs fully offline (no Java, no Hugging Face): boundary ADWIN falls back to the
DEV detector when CapyMOA is absent. For the canonical CapyMOA ADWIN run see
scripts/kaggle_drift_run.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C
from src import drift_analysis as DA

import pandas as pd

OUT = C.ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def main() -> None:
    boardings = DA.load_boardings()
    flags = DA.day_flags()
    print(f"[Role B feature table] {boardings.shape[0]:,} rows | "
          f"{boardings['timestamp'].min()} -> {boardings['timestamp'].max()}\n")

    # Per-stop weekday demand (mean boardings/day) + window length, used by the
    # reliability gate (config.MIN_DAILY_DEMAND / MIN_PEAK_DAYS). Several stops
    # carry ~no demand in this window, so a "peak" there is meaningless.
    _bd = boardings.copy()
    _bd["date"] = _bd["timestamp"].dt.normalize()
    _wk = _bd["timestamp"].dt.dayofweek < 5
    daily_demand = (_bd[_wk].groupby(["stop_id", "date"])["boardings"].sum()
                    .groupby("stop_id").mean().to_dict())
    n_window_days = int(_bd["date"].nunique())

    point_rows: list[dict] = []
    summary_rows: list[dict] = []
    drift_rows: list[dict] = []

    for stop_id, (label, _type) in C.STOPS.items():
        # ---------- Framing 1: data-driven boundaries ----------
        vol = round(float(daily_demand.get(str(stop_id), 0.0)), 1)
        for period in ("AM", "PM"):
            b = DA.boundaries_for_period(boardings, flags, stop_id, period)
            if b.empty:
                summary_rows.append({"stop": stop_id, "label": label, "period": period,
                                     "n_days": 0, "daily_boardings": vol,
                                     "coverage_pct": 0.0, "reliable": False})
                continue
            s = DA.segment_summary(b)
            drifts, backend = DA.boundary_drift(b)
            coverage = round(100.0 * s["n_days"] / max(n_window_days, 1), 1)
            reliable = (vol >= C.MIN_DAILY_DEMAND) and (s["n_days"] >= C.MIN_PEAK_DAYS)
            summary_rows.append({
                "stop": stop_id, "label": label, "period": period,
                "n_days": s["n_days"], "daily_boardings": vol,
                "coverage_pct": coverage, "reliable": reliable,
                "official": DA.fmt(OFFICIAL_MIN(period)),
                "weekday": DA.fmt(s["weekday"]), "weekend": DA.fmt(s["weekend"]),
                "holiday": DA.fmt(s["holiday"]),
                "weekend_shift_min": round(s["weekend_shift_min"], 1),
                "rain_shift_min": round(s["rain_shift_min"], 1),
                "boundary_drift_days": len(drifts), "detector": backend,
            })
            # Keep the flagged summary row for every stop, but only feed
            # RELIABLE (stop, period) series into the plotted boundary points.
            if not reliable:
                continue
            for _, r in b.iterrows():
                point_rows.append({
                    "stop": stop_id, "label": label, "period": period,
                    "date": r["date"].strftime("%Y-%m-%d"),
                    "start_min": int(r["start_min"]),
                    "weekend": int(bool(r["is_weekend"])),
                    "holiday": int(bool(r["is_holiday"])),
                    "rain": int(bool(r["is_rain"])),
                })

        # ---------- Framing 2: concept drift on Role C's ARF error ----------
        try:
            windows, backend, rmse = DA.concept_drift_from_windowed(stop_id)
            drift_rows.append({
                "stop": stop_id, "label": label, "model": DA.ARF_MODEL,
                "n_windows": int(len(rmse)), "n_drift_windows": len(windows),
                "drift_windows": ";".join(map(str, windows)) if windows else "",
                "detector": backend,
            })
        except Exception as exc:  # C metrics missing / malformed
            drift_rows.append({"stop": stop_id, "label": label, "error": repr(exc)})

    pd.DataFrame(point_rows).to_csv(OUT / "boundary_points_real.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(OUT / "ampm_summary_real.csv", index=False)
    # NOTE: write the offline Framing-2 result to its OWN file so it never
    # clobbers the canonical CapyMOA-ADWIN run in role_d_concept_drift.csv
    # (produced on Kaggle by scripts/kaggle_drift_run.py, that is what the
    # report and Role E's E2_drift_summary use).
    pd.DataFrame(drift_rows).to_csv(OUT / "role_d_concept_drift_offline.csv", index=False)

    print("Framing 1 (boundaries):")
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print("\nFraming 2 (concept drift on Role C ARF RMSE):")
    print(pd.DataFrame(drift_rows).to_string(index=False))
    print(f"\nWrote: boundary_points_real.csv, ampm_summary_real.csv, "
          f"role_d_concept_drift_offline.csv -> {OUT}")


def OFFICIAL_MIN(period: str) -> int:
    return DA.OFFICIAL[period]


if __name__ == "__main__":
    main()
