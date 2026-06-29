"""Role D, Framing 3 - scheduled-service vs realized-demand alignment.

Builds, per stop, the GTFS scheduled-arrival profile, finds the scheduled
peak window, and compares it to the data-driven demand peak (Framing 1).
The gap (minutes) is the actionable "is the timetable aligned with demand?"
number.

Run (needs the GTFS files + Role B feature table in the repo):
    python scripts/01_download_data.py     # once, to fetch gtfs/stop_times.txt
    python scripts/04_schedule_alignment.py

Outputs (tracked):
    outputs/schedule_alignment.csv          per stop/period/day-type + gap
    figures/schedule_<stop>.png             weekday AM profile + peak markers

Note: stop_times.txt is the *scheduled* timetable (not realized AVL arrivals),
so this is a descriptive supply-vs-demand layer, not an online-ML task. The
streaming requirement is satisfied by Framings 1 & 2.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import config as C
from src import schedule_alignment as SA

OUT = C.ROOT / "outputs"
FIG = C.FIGURES
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)


def main() -> None:
    # Load the heavy inputs once, reuse for table + plots.
    SA.ensure_gtfs()
    print("Loading GTFS stop_times (filtered to our stops)...")
    st = SA.load_stop_times(list(C.STOPS.keys()))
    trip_dt = SA.trip_daytypes()
    boardings = SA.load_boardings()
    flags = SA.day_flags()
    print(f"  scheduled arrivals kept: {len(st):,} rows across {st['stop_id'].nunique()} stops")

    table = SA.alignment_table(C.STOPS, st=st, trip_dt=trip_dt,
                               boardings=boardings, flags=flags)
    table.to_csv(OUT / "schedule_alignment.csv", index=False)

    show = ["stop", "label", "period", "day_type",
            "scheduled_peak", "demand_peak", "gap_min", "recommendation"]
    print("\nSchedule alignment (scheduled service peak vs demand peak):")
    print(table[show].to_string(index=False))
    print(f"\nWrote outputs/schedule_alignment.csv")

    # Figures: weekday AM scheduled profile + peak markers, for the start subset.
    for stop_id in C.START_SUBSET:
        label = C.STOPS[stop_id][0]
        prof = SA.scheduled_profile(st, trip_dt, stop_id, "weekday")
        if prof.sum() == 0:
            print(f"  [skip figure] no scheduled weekday arrivals for {stop_id}")
            continue
        sched = SA.scheduled_peak_start(prof, "AM")
        b = SA.boundaries_for_period(boardings, flags, stop_id, "AM")
        dem = SA.segment_summary(b).get("weekday", float("nan")) if not b.empty else float("nan")

        mins = [i * 5 for i in range(len(prof))]
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.bar(mins, prof, width=4.5, color="#1f77b4", alpha=0.7,
               label="scheduled arrivals / 5 min")
        if sched == sched:
            ax.axvline(sched, color="#1f77b4", ls="--", lw=2,
                       label=f"scheduled peak {SA.fmt(sched)}")
        if dem == dem:
            ax.axvline(dem, color="#d62728", ls="-", lw=2,
                       label=f"demand peak {SA.fmt(dem)}")
        ax.axvspan(C.AM_WINDOW[0], C.AM_WINDOW[1], color="grey", alpha=0.08)
        ax.set_xlim(0, 1440)
        ax.set_xticks(range(0, 1441, 120))
        ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
        ax.set_title(f"{label} ({stop_id}) - weekday: scheduled service vs demand peak")
        ax.set_xlabel("time of day")
        ax.set_ylabel("scheduled arrivals / 5 min")
        ax.legend(loc="upper right", fontsize=9)
        fig.tight_layout()
        out = FIG / f"schedule_{stop_id}.png"
        fig.savefig(out, dpi=140)
        plt.close(fig)
        print(f"  saved {out.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
