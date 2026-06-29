# Role C, Streaming modeling

**Owner:** Hans · **Status:** Completed

**Covers in the report:** Method §online model (CapyMOA regressor,
test-then-train), Experiments §model results (RMSE/MAE, baselines).

## Where the code lives (integrated)

The implementation is integrated into the main project as **`src/pipeline.py`**
(run with `python -m src.pipeline`). It reads Role B's canonical no-look-ahead
feature table at `docs/role_B_external_features/features_stream.csv` and writes
results to `outputs/role_c_cumulative_metrics.csv` and
`outputs/role_c_windowed_metrics.csv`.

A snapshot of the cumulative results table used in the report is kept here:
`role_c_cumulative_metrics.csv`.

## Purpose of Role C

Role C provides the online machine-learning modelling stage: it predicts
passenger boarding demand per stop with streaming regression models, evaluated
in a realistic online setting where each observation is predicted **before** the
model trains on the true value.

## Input data

Role C uses Role B's processed feature file (`features_stream.csv`) rather than
Role A's raw stream, because Role B's handover identified a target-leakage risk
in the early Role A stream (`boardings` appearing in both the feature vector and
the target). Role C uses only the safe feature columns and keeps `boardings`
solely as the target.

Target: `boardings`. Features: `hour_of_day, sin_hour, cos_hour, day_of_week,
is_weekend, is_holiday, boarding_lag_{1,2,3,6,12}, rolling_mean_{6,12},
rolling_std_{6,12}, precipitation_mm, temperature_2m, is_raining`. All lag/rolling
features use only past observations, so they are safe for prequential replay.

## Method (prequential / test-then-train)

For each 5-minute observation:

```
prediction = model.predict(x)
metrics.update(y_true, prediction)
model.train(x, y_true)
```

This prevents training on future data and matches the data-stream learning
requirement. Windowed metrics use 288-instance windows (one day of 5-minute
intervals).

## Models & baselines

CapyMOA models: `AdaptiveRandomForestRegressor` (main), `FIMTDD`,
`PassiveAggressiveRegressor`, `SGDRegressor`.

Online baselines (all use only already-seen data):
`baseline_previous_interval`, `baseline_rolling_mean_6`,
`baseline_last_week_same_interval` (2016 intervals = 1 week),
`baseline_official_window_mean` (separate running means for official peak /
off-peak).

## Main results summary

- **`baseline_previous_interval` is strongest overall**, short-term 5-minute
  boarding demand is highly autocorrelated, so the most recent count is a very
  strong predictor of the next interval.
- Among CapyMOA models, **`PassiveAggressiveRegressor` is best**, and it
  *beats* the previous-interval baseline at the busier, more variable **Lapa
  Station** (MAE 6.65 vs 7.22), evidence that adaptive online models help at
  high-variance hubs.
- `AdaptiveRandomForestRegressor` runs correctly and gives a valid comparison
  but does not beat the strongest simple baselines on this short horizon.
- **`SGDRegressor` and `FIMTDD` are unstable** (SGD diverges to ~1e11 errors,
  FIMTDD shows exploding RMSE). Treat as unreliable without further tuning
  (SGD almost certainly needs feature scaling / a smaller learning rate).

## Framing for the report

- Don't claim ARF was "the best model."
- Emphasise that every model was evaluated in a proper online stream setting
  with honest online baselines.
- Headline: short-term boarding demand is highly autocorrelated; the
  previous-interval baseline is strongest, Passive Aggressive is the best
  CapyMOA model, SGD/FIMTDD unstable.
- This does **not** weaken the project: peak-boundary detection (Role D) is the
  thesis; Role C's regression shows demand is predictable and that proper
  baselines were used.

## Reproducibility

```
python -m src.pipeline                           # ARF vs baselines, all 10 stops
python -m src.pipeline --models arf fimtdd pa sgd   # full all-model run
python -m src.pipeline --max-instances 2000      # quick debug run
```

Needs Java 17 + CapyMOA 0.13. Outputs land in `outputs/`. Seed fixed via
`config.SEED`.

## Files
- `role_c_cumulative_metrics.csv`, cumulative MAE/RMSE per stop (10 stops × 4
  CapyMOA models + 4 baselines = 80 rows); the main experiments table.
- Full + windowed results are regenerated into `outputs/` by `src/pipeline.py`.
