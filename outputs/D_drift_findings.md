# Role D, Findings (real data, CapyMOA ADWIN)

Integrated with the team data layer: Role B's `features_stream.csv` (boardings +
weekend/holiday/rain flags) and Role C's online ARF regressor. Two framings:
**Framing 1** = drift on the data-driven peak boundaries; **Framing 2** = concept
drift on Role C's prequential model error. Data span 2024-03-01 → 2024-05-31.
Reproduced by `scripts/03_drift_analysis.py` (local, integrated) and the CapyMOA
Kaggle kernels `concept-drifters-d-drift` (boundaries) + `concept-drifters-conceptdrift`
(model-error). All ADWIN numbers below are the real CapyMOA runs.

## Method (all streaming / online)
For each stop, the 5-minute boarding series is streamed through an online adaptive-threshold
peak detector (EWMA off-peak baseline, peak when value > mean + K·std and > mean + min-lift,
sustained ≥ 20 min, inside a morning 04:00–11:00 or evening 15:00–22:00 search window). The
detected per-day peak-start times are then fed to a **CapyMOA ADWIN** change detector to test
for drift across the period; results are segmented by weekday / weekend / holiday and correlated
with daily rainfall.

## Headline results

| Stop | Period | data-driven start (weekday) | official | weekend shift | ADWIN drift | days |
|---|---|---|---|---|---|---|
| Lapa Station | AM | **06:10** | 06:00 | +10 min | none | 62 |
| Salvador Bus Station | PM | **17:05** | 17:00 | +48 min | none | 53 |
| Lacerda Elevator | PM | 17:06 | 17:00 | +80 min | none | 36 |
| Shopping mall | PM | 15:57 | 17:00 | **+193 min** | none | 43 |
| Castro Alves Theater | PM | 17:21 | 17:00 | +89 min | none | 33 |

(Full table incl. AM/PM for all stops: `outputs/ampm_summary_real.csv`. Per-stop figures:
`ampm_<stop>.png` on the Kaggle kernel.)

## What the data actually says
1. **Morning rush is a clean signal only at the origin hub Lapa** (sharp 06:00–09:00 boarding
   surge): true start 06:10, ~10 min later than the official 06:00, and very stable.
2. **Evening rush is the universal boarding signal**, most stops peak in the evening (people
   boarding to go home), so PM boundary detection is where the results are.
3. **The dominant effect is the weekday→weekend shift**, not slow temporal drift. ADWIN flags
   **no within-period drift** anywhere across Mar–May, so for this 3-month window the story is
   *regime differences* (weekday vs weekend vs holiday, and stop type), which we should frame
   the project around rather than gradual drift.
4. **Weather is a weak signal here** because Mar–May is Salvador's wet season (68/92 days rainy).
   The one suggestive effect: Bus Station's evening peak starts ~30 min **earlier** on rainy days
   (plausible earlier home-rush); other rain numbers are noisy / few-day.
5. **Stop/signal caveats:** UFBA, Itapuã, Fonte Nova, Barradão have little/no morning boarding, UFBA's morning *arrival* is in the **alighting (landing)** series, not boarding. So a morning
   analysis of destination stops should use alighting.

## Framing 2, concept drift on the online model (uses Role C)
We fed Role C's online ARF regressor error into CapyMOA ADWIN two ways:
- **Per-instance |error| stream:** ADWIN fires almost every day (55–186 detections/stop).
  This is *not* meaningful drift, demand is strongly seasonal (big error at peaks, small
  at troughs), so ADWIN just tracks the within-day cycle. Reported as a caveat.
- **Per-day RMSE series (the right granularity):** ADWIN flags **0 drift days for every
  stop** → once ARF warms up, its daily error regime is stable across Mar–May.

This agrees with Framing 1 (boundary ADWIN = 0 drift). **Unified conclusion: there is no
temporal concept drift in this 3-month window**, neither the peak boundaries nor the
model's error regime drift. The real, actionable variation is *structural/cyclical*
(weekday vs weekend vs holiday, and stop type), which is what we build the story around.
(Full numbers: `outputs/role_d_concept_drift.csv`.)

## Actionable takeaway
The fixed official 06:00 / 17:00 windows miss the real picture. Examples an operator can act on:
- **Shopping mall:** reinforce the evening service ~16:00 on weekdays but ~19:00 on weekends.
- **Bus Station:** sharp evening peak at 17:05, starting ~48 min later at weekends.
- **Lapa:** morning reinforcement can start at ~06:10, not 05:45/06:00.
