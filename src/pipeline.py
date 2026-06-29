"""Role C - online (prequential) boarding regression  [INTEGRATED].

Owner: Hans (Role C). Reads Role B's no-look-ahead feature table
(`docs/role_B_external_features/features_stream.csv`), builds CapyMOA
RegressionInstances, and runs a proper test-then-train loop comparing
CapyMOA regressors against fully-online baselines. Cumulative + windowed
MAE/RMSE are written to `outputs/` for Role E / the report.

Boundary detection and drift are Role D's job (src/drift_analysis.py), not here.

Run (needs Java 17 + capymoa), from the repo root:
    python -m src.pipeline                         # ARF vs baselines, all 10 stops
    python -m src.pipeline --models arf fimtdd pa sgd
    python -m src.pipeline --max-instances 2000    # quick debug run
"""

## Role C - online prequential boarding regression.

## Uses Role B's features_stream.csv as the main input.

## Responsibilities:
## - reads Role B's no-lookahead streaming feature table
## - creates CapyMOA RegressionInstance objects manually
## - runs a proper prequential loop: predict -> score -> train
## - compares AdaptiveRandomForestRegressor against online baselines
## - writes cumulative and windowed MAE/RMSE CSV files for Role E / report


from __future__ import annotations

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import itertools

import config as C

import argparse
import csv
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

# Integrated defaults: read Role B's canonical feature table, write to tracked outputs/.
DEFAULT_FEATURES = C.ROOT / "docs" / "role_B_external_features" / "features_stream.csv"
DEFAULT_OUT_DIR = C.ROOT / "outputs"

FEATURE_COLS = [
    "hour_of_day", "sin_hour", "cos_hour", "day_of_week",
    "is_weekend", "is_holiday",
    "boarding_lag_1", "boarding_lag_2", "boarding_lag_3",
    "boarding_lag_6", "boarding_lag_12",
    "rolling_mean_6", "rolling_std_6", "rolling_mean_12", "rolling_std_12",
    "precipitation_mm", "temperature_2m", "is_raining",
]

TARGET_COL = "boardings"

STOP_IDS = [int(stop_id) for stop_id in C.STOPS.keys()]

STOP_NAMES = {
    int(stop_id): label
    for stop_id, (label, _stop_type) in C.STOPS.items()
}

def time_str_to_hour(time_str: str) -> float:
    hour, minute = time_str.split(":")
    return int(hour) + int(minute) / 60.0


## --------- Tracks MAE and RMSE incrementally.
@dataclass
class OnlineRegressionMetrics:
    name: str
    n: int = 0
    abs_error_sum: float = 0.0
    squared_error_sum: float = 0.0

    def update(self, y_true: float, y_pred: float | None) -> None:
        if y_pred is None:
            # Many online learners cannot predict before seeing data. Treating the
            # cold-start prediction as 0 is explicit and keeps baselines comparable.
            y_pred = 0.0
        error = float(y_true) - float(y_pred)
        self.n += 1
        self.abs_error_sum += abs(error)
        self.squared_error_sum += error * error

    def mae(self) -> float:
        return self.abs_error_sum / self.n if self.n else float("nan")

    def rmse(self) -> float:
        return math.sqrt(self.squared_error_sum / self.n) if self.n else float("nan")

    def snapshot(self, stop_id: int, model_name: str | None = None, window_id: int | None = None) -> dict:
        row = {
            "stop_id": int(stop_id),
            "stop_name": STOP_NAMES.get(int(stop_id), ""),
            "model": model_name or self.name,
            "n_instances": self.n,
            "MAE": self.mae(),
            "RMSE": self.rmse(),
        }
        if window_id is not None:
            row["window_id"] = window_id
        return row


## ----------- Predicts current boardings using the previous 5-minute interval.
class PreviousIntervalBaseline:
    name = "baseline_previous_interval"

    def __init__(self):
        self.last_y: float | None = None

    def predict(self, _x=None) -> float:
        return self.last_y if self.last_y is not None else 0.0

    def train(self, _x, y_true: float) -> None:
        self.last_y = float(y_true)


## ----------- Predicts using the mean of the last k observed boarding values.
class RollingMeanBaseline:
    def __init__(self, window_size: int = 6):
        self.window_size = int(window_size)
        self.values: deque[float] = deque(maxlen=self.window_size)
        self.name = f"baseline_rolling_mean_{self.window_size}"

    def predict(self, _x=None) -> float:
        if not self.values:
            return 0.0
        return float(sum(self.values) / len(self.values))

    def train(self, _x, y_true: float) -> None:
        self.values.append(float(y_true))


## ---------- Predicts using the same 5-minute interval one week earlier.
class LastWeekSameIntervalBaseline:
    name = "baseline_last_week_same_interval"

    def __init__(self, intervals_per_week: int = 2016):
        # 5-min intervals: 12/hour * 24/day * 7/week = 2016.
        self.history: deque[float] = deque(maxlen=int(intervals_per_week))

    def predict(self, _x=None) -> float:
        if len(self.history) < self.history.maxlen:
            return 0.0
        return float(self.history[0])

    def train(self, _x, y_true: float) -> None:
        self.history.append(float(y_true))


## ----------- Running mean baseline split by official rush-hour windows.
class OfficialWindowMeanBaseline:
    name = "baseline_official_window_mean"

    def __init__(self):
        self.peak_sum = 0.0
        self.peak_n = 0
        self.offpeak_sum = 0.0
        self.offpeak_n = 0

    @staticmethod
    def _is_peak(x: dict) -> bool:
        h = float(x["hour_of_day"])

        am_start = time_str_to_hour(C.OFFICIAL_AM[0])
        am_end = time_str_to_hour(C.OFFICIAL_AM[1])
        pm_start = time_str_to_hour(C.OFFICIAL_PM[0])
        pm_end = time_str_to_hour(C.OFFICIAL_PM[1])

        return (am_start <= h < am_end) or (pm_start <= h < pm_end)

    def predict(self, x: dict) -> float:
        if self._is_peak(x):
            return self.peak_sum / self.peak_n if self.peak_n else 0.0
        return self.offpeak_sum / self.offpeak_n if self.offpeak_n else 0.0

    def train(self, x: dict, y_true: float) -> None:
        if self._is_peak(x):
            self.peak_sum += float(y_true)
            self.peak_n += 1
        else:
            self.offpeak_sum += float(y_true)
            self.offpeak_n += 1


## ---------- Small adapter so CapyMOA learners match baseline predict/train methods.
class CapyMOARegressorWrapper:
    def __init__(self, name: str, learner, schema):
        self.name = name
        self.learner = learner
        self.schema = schema

    def _instance(self, x: dict, y: float):
        from capymoa.instance import RegressionInstance

        arr = np.array([float(x[c]) for c in FEATURE_COLS], dtype=np.float64)
        return RegressionInstance.from_array(self.schema, arr, float(y))

    def predict(self, x: dict) -> float | None:
        # RegressionInstance requires y_value, but the learner should not use it
        # during prediction. We pass a dummy 0.0 for the test instance.
        inst = self._instance(x, 0.0)
        return self.learner.predict(inst)

    def train(self, x: dict, y_true: float) -> None:
        inst = self._instance(x, float(y_true))
        self.learner.train(inst)

## -------------- Create a CapyMOA regression schema for Role B's numeric features.
def make_schema():
    from capymoa.stream import Schema

    # CapyMOA expects all attribute names, including the target. x arrays then
    # contain only feature values; RegressionInstance.from_array adds y_value.
    return Schema.from_custom(
        FEATURE_COLS + [TARGET_COL],
        target=TARGET_COL,
        name="SUNT_RoleB_BoardingRegression",
    )


## ----------- Build a CapyMOA regressor.
def make_capymoa_model(model_name: str, schema, seed: int = 42, ensemble_size: int = 10):
    model_name = model_name.lower()

    if model_name in {"arf", "adaptive_random_forest", "adaptive_random_forest_regressor"}:
        from capymoa.regressor import AdaptiveRandomForestRegressor

        learner = AdaptiveRandomForestRegressor(
            schema=schema,
            random_seed=seed,
            ensemble_size=ensemble_size,
            lambda_param=6.0,
        )
        return CapyMOARegressorWrapper(f"capymoa_arf_{ensemble_size}", learner, schema)

    if model_name in {"fim", "fimtd", "fimtdd"}:
        from capymoa.regressor import FIMTDD

        learner = FIMTDD(schema=schema)
        return CapyMOARegressorWrapper("capymoa_fimtdd", learner, schema)

    if model_name in {"pa", "passive_aggressive", "passiveaggressive"}:
        from capymoa.regressor import PassiveAggressiveRegressor

        learner = PassiveAggressiveRegressor(schema=schema)
        return CapyMOARegressorWrapper("capymoa_passive_aggressive", learner, schema)

    if model_name in {"sgd", "sgd_regressor"}:
        from capymoa.regressor import SGDRegressor

        learner = SGDRegressor(schema=schema)
        return CapyMOARegressorWrapper("capymoa_sgd", learner, schema)

    raise ValueError(f"Unknown model '{model_name}'. Use: arf, fimtdd, pa, sgd")


## --------- Load Aryan's (Role B) feature table and validate required columns.
def load_features(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Feature file not found: {path}")

    df = pd.read_csv(path, parse_dates=["timestamp"], low_memory=False)

    required = ["timestamp", "stop_id", TARGET_COL] + FEATURE_COLS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {path}: {missing}")

    # stop_id is intentionally kept integer. Booleans in FEATURE_COLS are safely
    # converted to 0.0/1.0 here to make instance creation consistent.
    for col in FEATURE_COLS:
        df[col] = df[col].astype(float)
    df[TARGET_COL] = df[TARGET_COL].astype(float)
    df["stop_id"] = df["stop_id"].astype(int)

    return df.sort_values(["stop_id", "timestamp"]).reset_index(drop=True)


## ---------- Yield one stop as a chronological stream of (timestamp, x_dict, y).
def iter_stop_rows(df: pd.DataFrame, stop_id: int) -> Iterable[tuple[pd.Timestamp, dict, float]]:
    sub = df[df["stop_id"] == int(stop_id)].sort_values("timestamp")
    for _, row in sub.iterrows():
        x = {col: float(row[col]) for col in FEATURE_COLS}
        y = float(row[TARGET_COL])
        yield row["timestamp"], x, y


## ---------- Run all learners and baselines for one stop.
def run_one_stop(
    df: pd.DataFrame,
    stop_id: int,
    model_names: list[str],
    max_instances: int | None,
    rolling_window: int,
    window_size: int,
    seed: int,
    ensemble_size: int,
) -> tuple[list[dict], list[dict]]:

    schema = make_schema()

    learners = [
        make_capymoa_model(name, schema, seed=seed, ensemble_size=ensemble_size)
        for name in model_names
    ]
    learners.extend([
        PreviousIntervalBaseline(),
        RollingMeanBaseline(window_size=rolling_window),
        LastWeekSameIntervalBaseline(),
        OfficialWindowMeanBaseline(),
    ])

    cumulative = {learner.name: OnlineRegressionMetrics(learner.name) for learner in learners}
    window_metrics = {learner.name: OnlineRegressionMetrics(learner.name) for learner in learners}

    cumulative_rows: list[dict] = []
    window_rows: list[dict] = []

    n = 0
    window_id = 0

    for _ts, x, y_true in iter_stop_rows(df, stop_id):
        # ---------- test phase ----------
        predictions = {}
        for learner in learners:
            predictions[learner.name] = learner.predict(x)

        for learner in learners:
            cumulative[learner.name].update(y_true, predictions[learner.name])
            window_metrics[learner.name].update(y_true, predictions[learner.name])

        # ---------- train/update phase ----------
        for learner in learners:
            learner.train(x, y_true)

        n += 1

        # Store window metrics at fixed intervals so Role E can plot drift over time.
        if window_size and n % window_size == 0:
            window_id += 1
            for learner in learners:
                window_rows.append(window_metrics[learner.name].snapshot(
                    stop_id=stop_id,
                    model_name=learner.name,
                    window_id=window_id,
                ))
                window_metrics[learner.name] = OnlineRegressionMetrics(learner.name)

        if max_instances is not None and n >= max_instances:
            break

    # Capture final partial window if it exists.
    if window_size:
        for learner in learners:
            if window_metrics[learner.name].n > 0:
                window_rows.append(window_metrics[learner.name].snapshot(
                    stop_id=stop_id,
                    model_name=learner.name,
                    window_id=window_id + 1,
                ))

    for learner in learners:
        cumulative_rows.append(cumulative[learner.name].snapshot(stop_id=stop_id))

    return cumulative_rows, window_rows


def write_csv(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    # Stable field ordering with any extras after.
    preferred = ["stop_id", "stop_name", "model", "window_id", "n_instances", "MAE", "RMSE"]
    extras = [k for k in rows[0].keys() if k not in preferred]
    fieldnames = [k for k in preferred if k in rows[0]] + extras

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


## ------------ Run experiments and write output CSV files.
def run_all(
    features: str | Path,
    out_dir: str | Path,
    stop_ids: list[int] | None = None,
    model_names: list[str] | None = None,
    max_instances: int | None = None,
    rolling_window: int = 6,
    window_size: int = 288,
    seed: int = C.SEED,
    ensemble_size: int = 10,
) -> tuple[list[dict], list[dict]]:

    model_names = model_names or ["arf"]
    stop_ids = stop_ids or STOP_IDS

    df = load_features(features)

    all_cumulative: list[dict] = []
    all_windowed: list[dict] = []

    for stop_id in stop_ids:
        print(f"\n=== Stop {stop_id} ({STOP_NAMES.get(int(stop_id), 'unknown')}) ===")
        cumulative, windowed = run_one_stop(
            df=df,
            stop_id=int(stop_id),
            model_names=model_names,
            max_instances=max_instances,
            rolling_window=rolling_window,
            window_size=window_size,
            seed=seed,
            ensemble_size=ensemble_size,
        )
        all_cumulative.extend(cumulative)
        all_windowed.extend(windowed)

        for row in cumulative:
            print(
                f"{row['model']:<38} "
                f"MAE={row['MAE']:.4f}  RMSE={row['RMSE']:.4f}  n={row['n_instances']}"
            )

    out_dir = Path(out_dir)
    cumulative_path = out_dir / "role_c_cumulative_metrics.csv"
    windowed_path = out_dir / "role_c_windowed_metrics.csv"

    write_csv(cumulative_path, all_cumulative)
    write_csv(windowed_path, all_windowed)

    print(f"\nSaved cumulative metrics: {cumulative_path}")
    print(f"Saved windowed metrics:   {windowed_path}")

    return all_cumulative, all_windowed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Role C CapyMOA prequential boarding regression")
    parser.add_argument("--features", default=str(DEFAULT_FEATURES), help="Path to Role B features_stream.csv")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Directory for output CSVs")
    parser.add_argument(
        "--stops",
        nargs="*",
        type=int,
        default=None,
        help="Optional stop IDs. Defaults to all 10 Role B stops.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["arf"],
        choices=["arf", "fimtdd", "pa", "sgd"],
        help="CapyMOA model(s) to evaluate.",
    )
    parser.add_argument("--max-instances", type=int, default=None, help="Limit per stop for debugging")
    parser.add_argument("--rolling-window", type=int, default=6, help="Rolling baseline window length")
    parser.add_argument("--window-size", type=int, default=288, help="Windowed metric size; 288 = one day")
    parser.add_argument("--seed", type=int, default=C.SEED, help="Random seed for CapyMOA learners")
    parser.add_argument("--ensemble-size", type=int, default=10, help="ARF ensemble size")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_all(
        features=args.features,
        out_dir=args.out_dir,
        stop_ids=args.stops,
        model_names=args.models,
        max_instances=args.max_instances,
        rolling_window=args.rolling_window,
        window_size=args.window_size,
        seed=args.seed,
        ensemble_size=args.ensemble_size,
    )
