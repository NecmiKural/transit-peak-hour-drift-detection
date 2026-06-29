"""Role D, exact, self-contained drift analysis as run on Kaggle.

This is the version-controlled copy of the Kaggle kernel
`necmikural/concept-drifters-d-drift` that produced our REAL results
(outputs/ampm_summary_real.csv, outputs/FINDINGS.md).

Why a separate self-contained script: CapyMOA needs Java 17 and the data
lives on Hugging Face. Kaggle has both (Java 17 + internet), while the Cowork
sandbox has neither, so the canonical real run happens on Kaggle. Paste this
into a Kaggle Python script kernel (internet ON), or run locally once
`pip install capymoa huggingface_hub holidays` and Java 17 are present.

It detects BOTH the morning (AM) and evening (PM) peak-start boundaries per
stop with an online adaptive-threshold detector, runs CapyMOA ADWIN on the
per-day boundary series to test for drift, segments by weekday/weekend/holiday,
and correlates with Open-Meteo daily rainfall. Outputs: ampm_summary_real.csv
and ampm_<stop>.png.
"""
import os
import subprocess, sys, math

subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "capymoa", "huggingface_hub", "holidays"])
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402
from capymoa.drift.detectors import ADWIN  # noqa: E402
import holidays as _hol  # noqa: E402
import requests  # noqa: E402

# Evidence-based stops: those with a real boarding peak (see outputs/FINDINGS.md).
STOPS = {
    "43768720": "Lapa Station",
    "258781031": "Salvador Bus Station",
    "44783914": "Lacerda Elevator",
    "47568123": "Shopping mall",
    "44072192": "Castro Alves Theater",
}
EWMA_ALPHA, THRESH_K, MIN_ABS, MIN_SUSTAIN, ADWIN_DELTA = 0.05, 2.5, 3.0, 4, 0.002
PERIODS = {"AM": ((4 * 60, 11 * 60), 6 * 60), "PM": ((15 * 60, 22 * 60), 17 * 60)}
# auto-detect Kaggle vs local; keeps the script runnable both places
OUT = "/kaggle/working" if os.path.isdir("/kaggle/working") else "outputs"
os.makedirs(OUT, exist_ok=True)

p = hf_hub_download(repo_id="labiaufba/SSA_StopBusTimeSeries_5",
                    filename="boarding_03-05_2024.csv", repo_type="dataset")
df = pd.read_csv(p)
tc = df.columns[0]
df[tc] = pd.to_datetime(df[tc])
df = df.set_index(tc).sort_index()
df.columns = [str(c) for c in df.columns]
print("DATA", df.shape, "|", df.index.min(), "->", df.index.max())


class Det:
    """Online adaptive-threshold peak-start detector for one time-of-day window."""

    def __init__(self, window):
        self.w = window
        self.mean = 0.0
        self.var = 1.0
        self.n = 0
        self.run = 0
        self.inpk = False
        self.pend = []
        self.cur = None
        self.ev = []

    def thr(self):
        return self.mean + THRESH_K * math.sqrt(max(self.var, 1e-9))

    def ewma(self, x):
        d = x - self.mean
        self.mean += EWMA_ALPHA * d
        self.var = (1 - EWMA_ALPHA) * (self.var + EWMA_ALPHA * d * d)

    def update(self, ts, v):
        self.n += 1
        mod = ts.hour * 60 + ts.minute
        inw = self.w[0] <= mod <= self.w[1]
        if self.n <= 200:
            self.ewma(v)
            return
        high = inw and v > self.thr() and v > self.mean + MIN_ABS
        if high:
            self.run += 1
            self.pend.append(ts)
            if not self.inpk and self.run >= MIN_SUSTAIN:
                st = self.pend[0]
                self.inpk = True
                self.cur = (str(ts.date()), st.hour * 60 + st.minute)
        else:
            if self.inpk and self.cur:
                self.ev.append(self.cur)
                self.cur = None
                self.inpk = False
            self.run = 0
            self.pend = []
            self.ewma(v)


def starts(stop, window):
    d = Det(window)
    for ts, v in df[stop].items():
        d.update(ts, float(v))
    o = pd.DataFrame(d.ev, columns=["date", "start_min"])
    if o.empty:
        return o
    o = o.groupby("date", as_index=False)["start_min"].min()
    o["date"] = pd.to_datetime(o["date"])
    o["is_weekend"] = o["date"].dt.dayofweek >= 5
    return o


hols = {d.isoformat() for d in _hol.Brazil(years=2024, subdiv="BA")}
d0, d1 = str(df.index.min().date()), str(df.index.max().date())
try:
    r = requests.get("https://archive-api.open-meteo.com/v1/archive",
                     params={"latitude": -12.9777, "longitude": -38.5016,
                             "start_date": d0, "end_date": d1,
                             "daily": "precipitation_sum", "timezone": "America/Bahia"},
                     timeout=40)
    wj = r.json()["daily"]
    wdf = pd.DataFrame({"date": pd.to_datetime(wj["time"]), "precip": wj["precipitation_sum"]})
    print("WEATHER days", len(wdf), "rainy(>1mm)", int((wdf.precip > 1).sum()))
except Exception as e:
    wdf = None
    print("WEATHER ERR", repr(e))


def fmt(m):
    return "--:--" if (m != m) else "%02d:%02d" % (int(m) // 60, int(m) % 60)


def mn(x):
    return float(x.start_min.mean()) if len(x) else float("nan")


rows = []
for stop, label in STOPS.items():
    fig, axes = plt.subplots(1, 2, figsize=(15, 4))
    for j, (per, (window, offv)) in enumerate(PERIODS.items()):
        b = starts(stop, window)
        if b.empty:
            rows.append({"stop": stop, "label": label, "period": per, "n_days": 0})
            axes[j].set_title("%s %s: none" % (label, per))
            continue
        b["is_holiday"] = b["date"].dt.strftime("%Y-%m-%d").isin(hols)
        if wdf is not None:
            b = b.merge(wdf, on="date", how="left")
            b["precip"] = b["precip"].fillna(0)
            b["is_rain"] = b["precip"] > 1
        wk = b[(~b.is_weekend) & (~b.is_holiday)].sort_values("date")
        we = b[b.is_weekend]
        ho = b[b.is_holiday]
        det = ADWIN(delta=ADWIN_DELTA)
        drifts = []
        for _, r2 in wk.iterrows():
            det.add_element(float(r2.start_min))
            if det.detected_change():
                drifts.append(str(r2.date.date()))
        s = {"stop": stop, "label": label, "period": per, "n_days": int(len(b)),
             "official": fmt(offv), "weekday": fmt(mn(wk)), "weekend": fmt(mn(we)),
             "holiday": fmt(mn(ho)), "weekend_shift_min": round(mn(we) - mn(wk), 1),
             "drift_days": len(drifts)}
        if wdf is not None and "is_rain" in b:
            dry, rain = wk[~wk.is_rain], wk[wk.is_rain]
            s["rain_shift_min"] = round(mn(rain) - mn(dry), 1)
        rows.append(s)
        print("==", label, "(%s)" % stop, per, "== official", s["official"],
              "| weekday", s["weekday"], "| weekend", s["weekend"],
              "(", s["weekend_shift_min"], "min) | drift", s["drift_days"], "| n", s["n_days"])
        ax = axes[j]
        ax.scatter(wk.date, wk.start_min, s=12, c="#1d4e89", label="weekday")
        ax.scatter(we.date, we.start_min, s=12, c="#e08a1e", label="weekend")
        if len(ho):
            ax.scatter(ho.date, ho.start_min, s=55, facecolors="none",
                       edgecolors="red", label="holiday")
        ax.set_title("%s -- %s start" % (label, per))
        ax.set_ylabel("minute of day")
        ax.legend(fontsize=7)
    fig.suptitle("%s (%s) [REAL | capymoa ADWIN]" % (label, stop))
    fig.tight_layout()
    fig.savefig("%s/ampm_%s.png" % (OUT, stop), dpi=110)
    plt.close(fig)

res = pd.DataFrame(rows)
res.to_csv("%s/ampm_summary_real.csv" % OUT, index=False)
print("=== SUMMARY (REAL, AM+PM, CapyMOA ADWIN) ===")
print(res.to_string(index=False))
print("--- done ---")
