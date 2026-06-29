# Role E, Evaluation, viz & reproducibility

**Owner:** Saurabh · **Status:** integrated into main project

Covers in the report: Experiments §evaluation + figures; the reproducibility
statement (seed, requirements, one-command run).

## Files dropped here
- `Evaluation.ipynb`, the evaluation/visualization notebook. Reads Role C
  (`outputs/role_c_*_metrics.csv`) and Role D (`outputs/*drift*`, boundary,
  schedule) outputs and produces the polished tables + the 6 report figures.

Generated artifacts (in the shared project folders):
- `figures/role_E_polished/`, 6 report-ready figures: average MAE/RMSE by
  model, windowed MAE/RMSE over time, detected peak start over time, schedule
  alignment gap.
- `outputs/role_E_polished/`, 5 summary tables: model comparison, best model
  per stop, peak-boundary summary, drift summary, readable boundary points.

## Key findings (for the report)

1. **Model comparison (Framing 1, regression).** Across the 10 stops the naive
   `previous-interval` baseline has the lowest error (mean RMSE ≈ 1.86),
   `rolling-mean-6` next (≈ 4.18), and the online **CapyMOA ARF (ensemble=10)**
   higher (≈ 8.15); the `official-window` and `last-week` baselines are far
   worse (15.2 / 26.7). At 5-min resolution the series is spiky and low-count,
   so persistence is hard to beat, to be framed honestly in the report (the
   streaming model's value is adaptivity, not raw accuracy here).
2. **Concept drift (Framing 2, real CapyMOA ADWIN on Kaggle).** Per-instance
   ADWIN on the ARF error fires constantly (55–186/stop) but only because it
   tracks the within-day demand cycle, a methodological caveat, not drift.
   ADWIN on the per-**day** RMSE series = **0 drift days for every stop**.
   **Conclusion: no temporal concept drift in this 3-month window;** the real,
   actionable variation is structural (weekday vs weekend vs holiday, and stop
   type), not slow drift. Consistent with Framing 1's boundary-drift result.

## Peak-boundary reliability gate (resolved)
The earlier draft showed implausible boundaries for some stops (e.g. UFBA
"morning peak" at ~10:40 on only 6 days; Itapuã/Fonte Nova/Barradão with 0
days). Investigation on the real data showed this is **demand truth, not a
detector bug**: in this Mar–May 2024 window several stops carry almost no
boardings (Arena Fonte Nova ~0/day, Barradão ~2, Itapuã ~36), and others rise
gradually with no sharp commuter spike, so there is no real "peak" to find.

Fix (`scripts/03_drift_analysis.py` + `config.MIN_DAILY_DEMAND` /
`MIN_PEAK_DAYS`): every (stop, period) now carries `daily_boardings`,
`coverage_pct` and a `reliable` flag. All rows are still written for
transparency, but only **reliable** (stop, period) series feed the plotted
boundary points. 10 of 20 (stop, period) combinations are reliable; the
headline boundary figure now shows **Lapa Station** (43,125 boardings/day,
62/66 weekdays detected): a real morning peak starting ~06:00–06:20, drifting
~05:40–06:40 day to day, ~10 min later on weekends. The model-comparison and
concept-drift conclusions were unaffected.

Note: `detector` still reads `DEV-fallback` because the offline pipeline ran
without Java; the canonical CapyMOA-ADWIN boundary/error run is
`scripts/kaggle_drift_run.py` (and `outputs/role_d_concept_drift.csv`, used for
`E2_drift_summary.csv`, is that real Kaggle result).
