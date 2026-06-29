"""DEV-ONLY synthetic fixture for building/validating the Role-D drift module
*before* the real Hugging Face CSVs are downloaded by Role A.

It writes a wide [timestamp x stop] boarding CSV in the SAME format as the
real `boarding_03-05_2024.csv`, plus a matching daily weather file, so the
whole drift-analysis pipeline can be exercised offline. The numbers are
fabricated, DO NOT use any output from this for the report. Swap in the
real CSV (data/raw/boarding_03-05_2024.csv) and re-run scripts/03.

It deliberately bakes in recoverable signals:
  * commuter/hub stops: sharp weekday AM + PM peaks; weak on weekends;
  * holidays (29 Mar, 21 Apr, 1 May 2024) behave like weekends;
  * leisure stop: midday bump, stronger on weekends/holidays;
  * on RAINY weekday mornings the commuter AM peak starts ~15 min earlier
    and ~30% heavier (the lecturer's "rainy day" hypothesis).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C

rng = np.random.default_rng(C.SEED)


def _bump(mod, center, width, amp):
    return amp * np.exp(-0.5 * ((mod - center) / width) ** 2)


def _profile(stype, mod, weekend, holiday, rain):
    off = weekend or holiday
    base = 1.0
    if "commuter" in stype or "hub" in stype or "intercity" in stype:
        am_c, am_w, am_a = 450, 35, 22         # ~07:30 weekday AM peak
        if rain and not off:
            am_c, am_a = 435, am_a * 1.3        # earlier + heavier in rain
        am = _bump(mod, am_c, am_w, am_a * (0.3 if off else 1.0))
        pm = _bump(mod, 1080, 45, 16 * (0.4 if off else 1.0))  # ~18:00
        return base + am + pm
    if "leisure" in stype or "tourist" in stype:
        mid = _bump(mod, 840, 120, (14 if off else 6))         # ~14:00, bigger on weekends
        return base + mid
    if "event" in stype:
        ev = _bump(mod, 1140, 40, (20 if weekend else 8))      # ~19:00 evenings
        return base + ev
    # commercial / default: broad daytime
    return base + _bump(mod, 780, 200, 8)


def main():
    idx = pd.date_range(C.DATE_START, "2024-05-31 23:55", freq=C.FREQ)
    mod = idx.hour * 60 + idx.minute
    dow = idx.dayofweek
    weekend = dow >= 5
    dates = idx.normalize()

    holidays = {pd.Timestamp(d) for d in ["2024-03-29", "2024-04-21", "2024-05-01"]}
    is_hol = np.array([d in holidays for d in dates])

    # rainy days: ~30% of days, fixed by seed; saved out for the weather merge
    uniq_days = pd.to_datetime(sorted(set(dates)))
    rain_days = set(rng.choice(uniq_days, size=int(0.3 * len(uniq_days)), replace=False))
    is_rain = np.array([d in rain_days for d in dates])

    out = pd.DataFrame(index=idx)
    out.index.name = "timestamp"
    for sid, (label, stype) in C.STOPS.items():
        mu = np.array([
            _profile(stype, m, w, h, r)
            for m, w, h, r in zip(mod, weekend, is_hol, is_rain)
        ])
        out[sid] = rng.poisson(np.clip(mu, 0.05, None)).astype(int)

    C.DATA_PROC.mkdir(parents=True, exist_ok=True)
    bpath = C.DATA_PROC / "synthetic_boarding.csv"
    out.to_csv(bpath)

    # daily weather fixture (precip_mm > 0 on the rainy days)
    wdf = pd.DataFrame({
        "date": [d.date() for d in uniq_days],
        "precip_mm": [round(float(rng.uniform(2, 20)), 1) if d in rain_days else 0.0
                      for d in uniq_days],
    })
    wpath = C.DATA_PROC / "synthetic_weather.csv"
    wdf.to_csv(wpath, index=False)

    print(f"[SYNTHETIC] wrote {bpath}  shape={out.shape}")
    print(f"[SYNTHETIC] wrote {wpath}  rainy_days={int(wdf.precip_mm.gt(0).sum())}/{len(wdf)}")
    print(f"[SYNTHETIC] holidays baked in: {sorted(str(h.date()) for h in holidays)}")


if __name__ == "__main__":
    main()
