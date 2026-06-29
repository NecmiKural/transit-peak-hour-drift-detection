# Role B, External data & features

**Owner:** Aryan · **Status:** delivered + integrated

**Covers in the report:** Method §features (streaming features, external data
merge: weather + holidays, no look-ahead).

## Files here (Role B's deliverables)

- `B_README.md`, Role B's full documentation (sources, columns, design notes).
- `Role_B_Handover_Notes.pdf`, handover notes for Roles C, D, F.
- `role_b_features.py`, the original authored Colab script (source of record).

## How it's integrated into the repo

The Colab logic was refactored into repo-native, importable modules so the
feature table is reproducible with one command (no Colab/Java needed):

- `src/features.py`, importable batch builder (`build_feature_table`,
  `build_features`, `merge_external`) + consumer helpers
  (`load_feature_table`, `iter_feature_rows`, `FEATURE_COLS`) + the online
  `StreamingFeatures` class.
- `scripts/02_build_features.py`, orchestrator: raw boarding + Open-Meteo
  weather (`external/weather.py`) + holidays (`external/holidays_ssa.py`)
  → regenerates the feature table in place.
- The three output CSVs are git-tracked **here** in
  `docs/role_B_external_features/`: `features_stream.csv` (primary,
  218,400 × 26), `weather_salvador.csv`, `holidays_2024.csv`.

### For Roles C / D

```python
from src.features import load_feature_table, iter_feature_rows, FEATURE_COLS

df = load_feature_table()                       # data/processed/features_stream.csv
for ts, x, y in iter_feature_rows(df, "43768720"):   # one stop, time-ordered
    # pred = model.predict(x); model.train(x, y)   # test-then-train
    ...
```
`stop_id` is stored as int64 in the CSV; `iter_feature_rows` accepts int or str.
