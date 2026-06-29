"""Plot AM/PM peak-start boundaries per stop from outputs/boundary_points_real.csv.

The boundary points were computed on the REAL data (CapyMOA run on Kaggle,
`scripts/kaggle_drift_run.py`); this script just renders them so the figures
live in the repo. Run: python scripts/plot_boundaries.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {sid: lab for sid, (lab, _t) in C.STOPS.items()}
OFFICIAL = {"AM": 6 * 60, "PM": 17 * 60}

src = C.ROOT / "outputs" / "boundary_points_real.csv"
b = pd.read_csv(src)
b["date"] = pd.to_datetime(b["date"])
XLIM = (pd.Timestamp("2024-03-01"), pd.Timestamp("2024-06-01"))

for stop, g in b.groupby("stop"):
    stop = str(stop)
    label = LABELS.get(stop, stop)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    for j, per in enumerate(["AM", "PM"]):
        ax = axes[j]
        ax.set_xlim(*XLIM)
        gp = g[g["period"] == per]
        if gp.empty:
            ax.set_title(f"{per}: no peak detected")
            ax.set_ylim(0, 1440)
            continue
        wk = gp[(gp.weekend == 0) & (gp.holiday == 0)]
        we = gp[gp.weekend == 1]
        ho = gp[gp.holiday == 1]
        ax.scatter(wk.date, wk.start_min, s=14, c="#1d4e89", label="weekday")
        ax.scatter(we.date, we.start_min, s=14, c="#e08a1e", label="weekend")
        if len(ho):
            ax.scatter(ho.date, ho.start_min, s=60, facecolors="none",
                       edgecolors="red", label="holiday")
        ax.axhline(OFFICIAL[per], color="grey", ls=":", lw=1,
                   label=f"official {OFFICIAL[per]//60:02d}:00")
        ax.set_title(f"{per} peak start  (n={len(gp)})")
        ax.set_ylabel("minute of day")
        ax.legend(fontsize=7)
    fig.suptitle(f"{label} ({stop}), real boarding, CapyMOA ADWIN (no drift flagged)")
    fig.tight_layout()
    out = C.FIGURES / f"ampm_{stop}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print("saved", out.name, f"({len(g)} pts)")
