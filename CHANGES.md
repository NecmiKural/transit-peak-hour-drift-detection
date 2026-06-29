# Dataset changes log

The brief requires that if we modify any dataset, we submit the modified
file(s) **and** describe the changes here. Log every transformation below.

| Date | File | Change | Reason | Author |
|---|---|---|---|---|
| 2024 (Role B) | `docs/role_B_external_features/features_stream.csv` | Derived feature table: raw boarding melted long, joined with Open-Meteo hourly weather (ffill to 5-min) + national holiday flags, plus calendar/cyclic/lag/rolling/rain features (no look-ahead). | Streaming-safe model input for Roles C/D. | Role B |
| 2024 (Role D) | `outputs/schedule_alignment.csv`, `figures/schedule_<stop>.png` | Derived from GTFS `stop_times.txt` (filtered to the 10 stops; `trips.txt`+`calendar.txt` map trips to weekday/weekend service) into a scheduled-arrival profile per stop, then scheduled-peak vs demand-peak gap. No raw file modified; read-only derivation. | Framing 3: scheduled service vs demand alignment. | Role D |
| 2024 (Role E) | `outputs/role_E_polished/*.csv`, `figures/role_E_polished/*.png` | Polished evaluation tables + 6 report figures derived from Role C/D outputs (model comparison, best-model-per-stop, peak-boundary & drift summaries, windowed-error & peak-boundary plots). | Report-ready evaluation & visualisation. No raw file modified; read-only derivation. | Role E |

Notes:
- Raw files are downloaded by `scripts/01_download_data.py` into `data/raw/`
  and are treated as read-only.
- Any cleaning/resampling writes to `data/processed/` and is recorded above.
