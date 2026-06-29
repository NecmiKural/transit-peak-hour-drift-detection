# Role D, Change-point / drift

**Owner:** necmi · **Status:** DONE, integrated with B + C, both framings, real CapyMOA ADWIN

Drop here the document(s) this role produces (any format) **and supporting
files** (boundary tables, drift plots, ADWIN/Page-Hinkley outputs).

**Covers in the report:** Related work, Method §boundary detection + drift,
Experiments §drift results (weekday/weekend/holiday, rain), Discussion.

**Suggested file naming:** `D_<topic>_<name>.<ext>`.

## Integration (team data layer)
- **Input = Role B** `features_stream.csv` (boardings + weekend/holiday/rain flags), same
  table Role C consumes, so D/B/C stay consistent.
- **Framing 2 input = Role C** online ARF regressor error (the C→D handoff).
- `src/drift_analysis.py` reads B's table; `scripts/03_drift_analysis.py` runs both framings
  offline (DEV detector); the canonical CapyMOA ADWIN runs are the two Kaggle kernels.

## What's done
**Framing 1, data-driven peak boundaries (signal-level drift)**
- Findings: [`outputs/D_drift_findings.md`](../../outputs/D_drift_findings.md).
- Tables: [`outputs/ampm_summary_real.csv`](../../outputs/ampm_summary_real.csv) (AM+PM per stop),
  [`outputs/boundary_points_real.csv`](../../outputs/boundary_points_real.csv) (per-day points).
- Figures: `figures/ampm_<stop>.png` (regenerated locally via `scripts/plot_boundaries.py`).
- Code: `src/peaks.py`, `src/drift.py`, `src/drift_analysis.py`, `scripts/03_drift_analysis.py`.
- Cloud: `scripts/kaggle_drift_run.py` (kernel `concept-drifters-d-drift`).

**Framing 2, concept drift on Role C's model error**
- Table: [`outputs/role_d_concept_drift.csv`](../../outputs/role_d_concept_drift.csv).
- Cloud: Kaggle kernel `concept-drifters-conceptdrift` (ARF prequential + CapyMOA ADWIN).

## Headline
Lapa morning peak 06:10 (vs official 06:00), stable; evening peak is the universal signal
(Bus Station 17:05, Mall, etc.); biggest effect is the weekday→weekend shift (Mall +193 min).
**Both framings agree: ADWIN finds 0 temporal drift** (boundaries stable; ARF daily-error
regime stable) → the story is *structural/cyclical* differences (weekday/weekend/holiday,
stop type), not slow drift. (Per-instance ADWIN-on-error fires constantly = seasonality, a
documented caveat, not a result.)

## For Role F (report + slides)
[`D_report_handover.md`](D_report_handover.md), report-ready Method/Results/Discussion
prose, the actionable takeaways, which figures to use, suggested slides, and a CRediT line.

## Reproducibility (whole project)
- **Environment:** Python ≥ 3.10 + **Java 17** (CapyMOA wraps MOA via JPype). Pinned
  versions in `requirements.txt` (capymoa==0.13.0). Random seed = `config.SEED` (42).
- **One command:** `python run_all.py` runs the full chain in order
  (download → features → Role C model → Role D drift → Role D schedule → Role E figures);
  `--skip-download`, `--only <stage>`, `--keep-going` flags available.
- **All intermediate outputs and the Role B feature table are git-tracked**, so the results
  can be verified without re-running anything. The offline data layer was sanity-checked
  to load the committed feature table (218,400 rows, all 10 stops, 92 days, Mar–May 2024).
- **Which drift result is canonical:** the reported Framing-2 numbers are the **CapyMOA
  ADWIN** run in [`outputs/role_d_concept_drift.csv`](../../outputs/role_d_concept_drift.csv)
  (Kaggle kernel, Java 17). Running `scripts/03_drift_analysis.py` locally **without** Java 17
  falls back to a DEV change-detector and writes `role_d_concept_drift_offline.csv`, that
  file is for offline development only and is **not** the result cited in the report. Framing-1
  boundary results (`ampm_summary_real.csv`, `boundary_points_real.csv`) reproduce offline from
  the committed feature table.
