# Role A - integration review (v2, tested on Kaggle)

A delivered a revised v2 after the first review. v2 is now the canonical Role A
deliverable in this folder (`process_sunt.py`, `A_README.md`, `output_log.md`,
`eda_plots/`). We re-ran the CapyMOA handle on Kaggle (real data, Java 17 +
capymoa 0.13). Verdict: v2 fixes everything from the first review and runs
end-to-end. One small leakage nit remains (item below), to fix before C/D train.

## v2 status of the earlier issues (all addressed)

1. Hard-coded peak label (`target_peak_class`): REMOVED. Target is now `boardings`
   (regression). Good.
2. 3.5x rush-hour weight: REMOVED from the data layer. Good.
3. `stop_id` dropped: FIXED. The handle now exposes one stream per stop
   (`get_stop_stream(stop_id)` / `get_all_stop_streams()`).
4. Broken CapyMOA API: FIXED. `Schema.from_custom(features, target, name=)` and
   `RegressionInstance.from_array(...)` were tested on Kaggle and work
   (capymoa 0.13.0, schema reports 6 attributes + numeric target,
   `is_regression() == True`, a regressor predict/train smoke test passed).
5. Robustness: ADDED. Per-chunk CSV row-count desync guard + explicit timestamp
   format guard.
6. Audit numbers: now self-consistent and printed by the script
   (261,600 total = 218,400 real + 43,200 imputed; availability 83.49%).

## One remaining fix (minor, before modelling)

The per-instance feature vector includes the **target** (`boardings`) as its last
element:
```python
x = np.array([hour, minute, day_of_week, alightings, occupancy_load, data_valid,
              boardings], dtype=np.float64)   # boardings is also y
yield RegressionInstance.from_array(schema=schema, x=x, y_value=boardings)
```
The schema has 6 input attributes (target excluded), so `x` should carry only
those 6 features. Including `boardings` in `x` is redundant and risks target
leakage (the model would see the answer as an input). It does not crash - both
the 6- and 7-element forms construct an instance on Kaggle - but C/D must use the
6-feature form. One-line fix: drop the trailing `boardings` from `x` (keep it only
as `y_value`); `_FEATURE_NAMES` can keep `boardings` last for the schema.

## Adopted (good work)

HF download + local cache, chunked O(1) streaming, online EWMA gap imputation,
March-May 2024 window filter, 10 per-stop weekday/weekend EDA profiles, clear
per-stop `RegressionInstance` handle for C/D. Comments are intentionally verbose
(A's note) and can be trimmed once the end-to-end pipeline is green.
