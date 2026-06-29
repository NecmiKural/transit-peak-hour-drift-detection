# Role D → Report/Slides Handover (for Role F)

Self-contained hand-off so F can drop D's part straight into the paper and the
slide deck. Numbers are the real CapyMOA runs; figures are in `figures/`.

---

## 1. One-line summary
We detect, fully online, *where the real peak-hour boundaries are* and *whether
they drift*, two ways (on the data signal, and on Role C's model error), and
find the boundaries and the model's error regime are **temporally stable**; the
real variation is **structural** (weekday vs weekend vs holiday, and stop type).

## 2. Method (report-ready prose)
We frame peak-hour boundary detection as a streaming change-detection problem and
attack it from two complementary angles, both consuming Role B's no-look-ahead
feature stream (`features_stream.csv`), the same input Role C's model uses.

**Framing 1, data-driven boundaries (signal level).** For each stop we stream the
5-minute boarding counts through an online adaptive-threshold detector: an EWMA
keeps a running off-peak mean and variance, and an interval is flagged "peak" when
its boarding rate exceeds `mean + k·std` and an absolute lift, sustained for ≥20 min,
inside a morning (04:00–11:00) or evening (15:00–22:00) search window. The first
sustained crossing each day is the data-driven peak *start*. The resulting per-day
boundary series is then monitored with **CapyMOA ADWIN** to test for temporal drift.

**Framing 2, concept drift on the online model (model level).** We take Role C's
online Adaptive Random Forest regressor and feed its prequential error into ADWIN,
both per-instance and as a per-day RMSE series, to detect when the model's error
regime shifts (classic concept drift).

Everything is single-pass / incremental, satisfying the streaming constraint; ADWIN
is the MOA/CapyMOA detector taught in the course.

## 3. Results (with the figures to use)
Per-stop boundary table: `outputs/ampm_summary_real.csv`; per-day points:
`outputs/boundary_points_real.csv`; figures: `figures/ampm_<stop>.png`.

| Stop | data-driven peak | official | weekend shift |
|---|---|---|---|
| Lapa Station (AM) | **06:09** | 06:00 | +11 min |
| Salvador Bus Station (PM) | **17:05** | 17:00 | +48 min |
| Shopping Mall (PM) | **15:57** | 17:00 | **+193 min** |
| Castro Alves Theater (PM) | 17:20 | 17:00 | +89 min |
| Lacerda Elevator (PM) | 17:06 | 17:00 | +72 min |

- **Morning rush is a clean signal only at the origin hub Lapa** (06:09, stable).
- **Evening rush is the universal boarding signal** (people boarding to go home);
  PM is where most stops have a peak.
- **Biggest, most consistent effect = the weekday→weekend shift** (Mall's evening
  peak slides ~3 h later at weekends).
- **Drift:** ADWIN finds **0 temporal drift** on the boundary series (Framing 1)
  *and* **0 drift** on the model's per-day RMSE (Framing 2). Per-instance ADWIN-on-error
  fires almost daily, but that is just the strong daily seasonality, a methodological
  caveat, not real drift. Numbers: `outputs/role_d_concept_drift.csv`.

## 4. Discussion / limitations (report-ready)
The 3-month window (Mar–May 2024) shows no slow temporal drift, so the project's
contribution is identifying the *structural* boundary differences and the gap between
official (06:00/17:00) windows and the true, stop-specific peaks. Limitations: it is a
3-month, 10-stop subset (no carnival); rain is a weak covariate because Mar–May is
Salvador's wet season (≈74% of days rainy); destination stops (e.g. UFBA) carry their
morning signal in *alighting*, not boarding, so a morning analysis there would use the
alighting series.

## 5. Actionable takeaways (the "so what")
- **Shopping Mall:** evening reinforcement should start ~16:00 on weekdays but ~19:00
  at weekends, a fixed 17:00 window is wrong both ways.
- **Bus Station:** sharp evening peak at 17:05, ~48 min later at weekends.
- **Lapa:** morning reinforcement can begin ~06:10, matching the true ramp.

## 6. Suggested slides (D contributes ~2–3)
1. **"Official vs real peak"**, title claim + the Lapa AM and Mall PM figures
   (`figures/ampm_43768720.png`, `figures/ampm_47568123.png`). Bullet: official
   06:00/17:00 miss the real, stop-specific boundaries.
2. **"Boundaries shift by day-type, not over time"**, the Mall figure (weekday vs
   weekend split) + one line: ADWIN = 0 temporal drift (both framings) → variation is
   structural (weekday/weekend/holiday), not drift.
3. *(optional)* **"We looked for drift two ways"**, Framing 1 (boundary series) +
   Framing 2 (model error); both stable; per-instance caveat in one line.

## 7. CRediT line for D
"D.: change-point/drift methodology; online boundary detector and ADWIN drift analysis
(signal- and model-level); drift figures and results."

## 8. Reproducibility
- Local (offline, DEV detector): `python scripts/03_drift_analysis.py` then
  `python scripts/plot_boundaries.py`.
- Canonical CapyMOA (Java 17): Kaggle kernels `concept-drifters-d-drift` (boundaries)
  and `concept-drifters-conceptdrift` (model-error); scripted in
  `scripts/kaggle_drift_run.py`. Seed = student ID (`config.SEED`).
