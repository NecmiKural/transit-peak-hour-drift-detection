"""
process_sunt.py, Role A: Data & EDA Lead
COMPX523 Assignment 3 | Team: Concept Drifters

Responsibilities:
    - Programmatic ingestion of the 10-stop SUNT subset from Hugging Face
    - Incremental (O(1) memory) streaming with in-stream gap imputation
    - Online EDA: per-stop hourly boarding profiles (weekday vs weekend)
    - Downstream handle: one per-stop RegressionInstance generator per stop,
      yielding native CapyMOA 0.13 objects ready for Roles C and D

Changes from original (see to_be_revised.md):
    [1] Removed hard-coded target_peak_class label, peak detection is Role D's job.
    [2] Removed hard-coded 3.5x rush-hour instance_weight, weighting is a modelling
        decision for Roles C/D, not part of ingestion.
    [3] Downstream handle now exposes one generator per stop (per-stop streams),
        not a single interleaved stream, so models can operate stop-by-stop.
    [4] CapyMOA target changed from LabeledInstance (peak class) to
        RegressionInstance with y = boardings, matching the project framing.
    [5] API calls updated to verified CapyMOA 0.13 signatures:
          Schema.from_custom()          (not from_custom_attributes)
          RegressionInstance.from_array(schema, x, y_value)  (no weight param)
    [6] Added timestamp format guard and explicit CSV row-count desync detection.
        Gap count is computed and printed so README availability figures are
        reproducible from the script output.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Environment flags, suppress noisy Hugging Face warnings before any import
# ---------------------------------------------------------------------------
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN_WARNING"] = "1"

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pandas.core.tools.datetimes")

from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Auto-install missing dependencies (safe for fresh Colab / VS Code envs)
# ---------------------------------------------------------------------------
_REQUIRED = {
    "huggingface_hub": "huggingface_hub",
    "pyarrow":         "pyarrow",
    "pandas":          "pandas",
    "matplotlib":      "matplotlib",
    "seaborn":         "seaborn",
}

print("Checking Python environment dependencies...")
for _mod, _pkg in _REQUIRED.items():
    try:
        __import__(_mod)
    except ImportError:
        print(f"  Installing missing package: {_pkg} ...")
        ret = os.system(f'"{sys.executable}" -m pip install --quiet {_pkg}')
        if ret != 0:
            print(f"  WARNING: pip install {_pkg} returned non-zero exit code.")
print("Dependency check complete.\n")

# ---------------------------------------------------------------------------
# Core imports (safe after dependency check)
# ---------------------------------------------------------------------------
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")          # headless backend, no Tkinter dependency
import matplotlib.pyplot as plt
import seaborn as sns

# ---------------------------------------------------------------------------
# CapyMOA import (optional, graceful fallback when Java 17 is absent)
# ---------------------------------------------------------------------------
try:
    with open(os.devnull, "w") as _devnull:
        _old_stderr, sys.stderr = sys.stderr, _devnull
        import capymoa                                       # noqa: F401
        from capymoa.stream import Schema
        from capymoa.instance import RegressionInstance
        sys.stderr = _old_stderr
    HAS_CAPYMOA = True
    print(f"CapyMOA {capymoa.__version__} bound successfully.")
except Exception:
    sys.stderr = _old_stderr if "_old_stderr" in dir() else sys.stderr
    HAS_CAPYMOA = False
    print("WARNING: CapyMOA not found. Downstream CapyMOA handle will be unavailable.")
    print("         Install Java 17 and run: pip install capymoa==0.13.0\n")

# Reproducibility seed (project-wide)
np.random.seed(42)

# Plot aesthetics
sns.set_theme(style="ticks")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["font.size"] = 11


# ===========================================================================
# MODULE 1, Workspace Initialisation & Programmatic Data Ingestion
# ===========================================================================

base_dir = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()

HF_REPO_ID = "labiaufba/SSA_StopBusTimeSeries_5"

# Keys must match column names present in the CSVs
DATASET_FILES = {
    "boarding": "boarding_03-05_2024.csv",
    "landing":  "landing_03-05_2024.csv",
    "loader":   "loader_03-05_2024.csv",
}

# 10-stop production set: stop_id -> (human label, plot colour)
ALL_STOPS = {
    "43768720":  ("Lapa Station Hub",            "#1f77b4"),
    "44783654":  ("UFBA University Gate",         "#2ca02c"),
    "230565994": ("Itapua Beach Leisure",         "#ff7f0e"),
    "125960550": ("Arena Fonte Nova Stadium",     "#d62728"),
    "45833547":  ("Barradao Stadium",             "#9467bd"),
    "44784438":  ("Ferry Terminal",               "#8c564b"),
    "47568123":  ("Shopping Mall Corridor",       "#e377c2"),
    "44072192":  ("Castro Alves Theater",         "#7f7f7f"),
    "258781031": ("Salvador Bus Station Terminal","#bcbd22"),
    "44783914":  ("Lacerda Elevator Tourist",     "#17becf"),
}

local_cache_dir = base_dir / "data_cache"
local_cache_dir.mkdir(exist_ok=True)

plots_out_dir = base_dir / "eda_plots"
plots_out_dir.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Data download
# ---------------------------------------------------------------------------
print("--- Phase 1: Data Ingestion ---")

# Silence the HF hub import-time token warning
try:
    with open(os.devnull, "w") as _devnull:
        _old_stderr, sys.stderr = sys.stderr, _devnull
        from huggingface_hub import hf_hub_download
        sys.stderr = _old_stderr
except Exception:
    sys.stderr = _old_stderr if "_old_stderr" in dir() else sys.stderr
    from huggingface_hub import hf_hub_download

local_csv_paths: dict[str, Path] = {}

for file_key, file_name in DATASET_FILES.items():
    local_fallback = local_cache_dir / file_name
    # Skip network call if file already cached locally
    if local_fallback.exists():
        print(f"  Using cached file: {file_name}")
        local_csv_paths[file_key] = local_fallback
        continue
    try:
        print(f"  Downloading from Hugging Face: {file_name} ...")
        with open(os.devnull, "w") as _devnull:
            _old_stderr, sys.stderr = sys.stderr, _devnull
            downloaded = hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=file_name,
                repo_type="dataset",
                local_dir=local_cache_dir,
            )
            sys.stderr = _old_stderr
        local_csv_paths[file_key] = Path(downloaded)
        print(f"    Saved to: {Path(downloaded).name}")
    except Exception as exc:
        sys.stderr = _old_stderr if "_old_stderr" in dir() else sys.stderr
        print(f"  WARNING: Download failed for '{file_name}': {exc}")
        if local_fallback.exists():
            print(f"    Falling back to cached copy.")
            local_csv_paths[file_key] = local_fallback
        else:
            print(f"  ERROR: '{file_name}' unavailable online and no local cache found. Aborting.")
            sys.exit(1)

print("Phase 1 complete. All CSV assets located.\n")


# ===========================================================================
# MODULE 2, Incremental Stream Generator
# ===========================================================================

# Expected timestamp format in the raw CSVs
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_timestamp(raw: str, fmt: str = _TS_FORMAT) -> datetime:
    """Parse a timestamp string, stripping whitespace.

    Raises ValueError with a clear message on format mismatch so that
    corrupt rows surface immediately rather than silently propagating NaT.
    """
    raw = raw.strip()
    try:
        return datetime.strptime(raw, fmt)
    except ValueError:
        raise ValueError(
            f"Timestamp '{raw}' does not match expected format '{fmt}'. "
            "Check whether the CSV file format has changed."
        )


class IncrementalTransitStreamer:
    """Simulates a live 5-minute telemetry feed from 10 Salvador transit stops.

    Design properties:
    - O(1) memory: data is processed in micro-chunks of `chunk_size` rows;
      no full CSV is ever held in RAM simultaneously.
    - In-stream gap imputation: if a 5-minute slot is absent from the file,
      a synthetic record is injected using an incremental cyclic EWMA baseline
      computed from previously seen values at the same time-of-day.
    - CSV desync guard: row counts across the three CSV files (boarding,
      landing, loader) are checked per-chunk; a mismatch raises immediately
      rather than silently pairing wrong rows via zip().
    - No hard-coded labels or weights: _package_instance returns only raw
      sensor values plus calendar features. Peak detection and weighting are
      downstream responsibilities (Roles C and D).
    """

    # Strict window defined by the assignment brief (March–May 2024)
    _WINDOW_START = datetime(2024, 3, 1,  0,  0,  0)
    _WINDOW_END   = datetime(2024, 5, 31, 23, 55,  0)

    def __init__(self, time_window_minutes: int = 5, chunk_size: int = 1000):
        self.interval_delta = timedelta(minutes=time_window_minutes)
        self.chunk_size     = chunk_size

        # Tracks the last timestamp emitted so gap injection knows where to start
        self._last_ts: datetime | None = None

        # Cyclic EWMA memory: {"HH:MM": {stop_id: float}}
        self._cyclic_memory: dict[str, dict[str, float]] = {}
        self._alpha = 0.05  # EWMA smoothing factor

    # ------------------------------------------------------------------
    # Cyclic EWMA helpers
    # ------------------------------------------------------------------

    def _cyclic_get(self, ts: datetime, stop_id: str) -> float:
        """Return the EWMA baseline for (time-of-day, stop_id), or 0.0."""
        key = ts.strftime("%H:%M")
        return self._cyclic_memory.get(key, {}).get(stop_id, 0.0)

    def _cyclic_update(self, ts: datetime, stop_id: str, value: float) -> None:
        """Update the EWMA baseline for (time-of-day, stop_id) incrementally."""
        key = ts.strftime("%H:%M")
        bucket = self._cyclic_memory.setdefault(key, {})
        if stop_id not in bucket:
            bucket[stop_id] = value
        else:
            bucket[stop_id] += self._alpha * (value - bucket[stop_id])

    # ------------------------------------------------------------------
    # Core stream generator
    # ------------------------------------------------------------------

    def generate_stream(self):
        """Yield one record dict per (timestamp, stop_id) pair in time order.

        Records are dicts with keys:
            timestamp        datetime, UTC-3 Salvador local time
            stop_id          str, GTFS stop identifier
            hour             float, hour of day  [0, 23]
            minute           float, minute       [0, 55]
            day_of_week      float, Mon=0 … Sun=6
            boardings        float, estimated boardings in this 5-min slot
            alightings       float, estimated alightings
            occupancy_load   float, passenger load on departing vehicle
            data_valid       int, 1 = real sensor value, 0 = imputed
        """
        stop_columns = list(ALL_STOPS.keys())

        iter_b  = pd.read_csv(local_csv_paths["boarding"], chunksize=self.chunk_size)
        iter_l  = pd.read_csv(local_csv_paths["landing"],  chunksize=self.chunk_size)
        iter_ld = pd.read_csv(local_csv_paths["loader"],   chunksize=self.chunk_size)

        print("--- Phase 2: Streaming ---")

        for chunk_b, chunk_l, chunk_ld in zip(iter_b, iter_l, iter_ld):

            # ----------------------------------------------------------
            # [Fix 6] Desync guard: all three CSVs must have the same
            # number of rows in every aligned chunk.
            # ----------------------------------------------------------
            if not (len(chunk_b) == len(chunk_l) == len(chunk_ld)):
                raise RuntimeError(
                    f"CSV row-count desync detected in chunk starting near row "
                    f"{chunk_b.index[0]}: boarding={len(chunk_b)}, "
                    f"landing={len(chunk_l)}, loader={len(chunk_ld)}. "
                    "The three CSV files may have different numbers of rows."
                )

            records_b  = chunk_b.to_dict(orient="records")
            records_l  = chunk_l.to_dict(orient="records")
            records_ld = chunk_ld.to_dict(orient="records")

            for row_b, row_l, row_ld in zip(records_b, records_l, records_ld):

                # ----------------------------------------------------------
                # [Fix 6] Timestamp parsing with explicit format guard.
                # Pull from the first column by position to avoid column-name
                # dependency (handles any column header the CSV might use).
                # ----------------------------------------------------------
                raw_ts_str = str(next(iter(row_b.values())))
                ts = _parse_timestamp(raw_ts_str)

                # Drop rows outside the assignment window
                if not (self._WINDOW_START <= ts <= self._WINDOW_END):
                    continue

                # ----------------------------------------------------------
                # In-stream gap imputation
                # If a 5-min slot was skipped, inject synthetic records using
                # the EWMA baseline so downstream models never see time jumps.
                # ----------------------------------------------------------
                if self._last_ts is not None:
                    expected = self._last_ts + self.interval_delta
                    while ts > expected:
                        for sid in stop_columns:
                            imputed = self._cyclic_get(expected, sid)
                            yield self._package_instance(
                                expected, sid, imputed, 0.0, 0.0, data_valid=0
                            )
                        self._last_ts = expected
                        expected     = self._last_ts + self.interval_delta

                # ----------------------------------------------------------
                # Emit real sensor records for every production stop
                # ----------------------------------------------------------
                for sid in stop_columns:
                    b_val  = max(0.0, float(row_b.get(sid,  0.0) or 0.0))
                    l_val  = max(0.0, float(row_l.get(sid,  0.0) or 0.0))
                    ld_val = max(0.0, float(row_ld.get(sid, 0.0) or 0.0))

                    self._cyclic_update(ts, sid, b_val)
                    yield self._package_instance(ts, sid, b_val, l_val, ld_val, data_valid=1)

                self._last_ts = ts

    # ------------------------------------------------------------------
    # Record factory
    # ------------------------------------------------------------------

    @staticmethod
    def _package_instance(
        ts: datetime,
        stop_id: str,
        boardings: float,
        alightings: float,
        occupancy_load: float,
        data_valid: int,
    ) -> dict:
        """Return a plain dict of sensor + calendar features.

        No target labels and no instance weights are set here.
        Peak detection is performed by Role D (src/peaks.py).
        Weighting decisions belong to Roles C and D.
        """
        return {
            "timestamp":      ts,
            "stop_id":        stop_id,
            "hour":           float(ts.hour),
            "minute":         float(ts.minute),
            "day_of_week":    float(ts.weekday()),   # Mon=0, Sun=6
            "boardings":      boardings,
            "alightings":     alightings,
            "occupancy_load": occupancy_load,
            "data_valid":     data_valid,
        }


# ===========================================================================
# MODULE 3, Online EDA: Incremental Hourly Profile Accumulation & Plots
# ===========================================================================

if __name__ == "__main__":

    print("--- Phase 3: Online EDA Accumulation ---")

    # Accumulators: stop -> day_type -> hour -> [running_sum, count]
    _eda: dict[str, dict[str, dict[int, list]]] = {
        sid: {
            "Weekday": {h: [0.0, 0] for h in range(24)},
            "Weekend": {h: [0.0, 0] for h in range(24)},
        }
        for sid in ALL_STOPS
    }

    streamer = IncrementalTransitStreamer()
    stream   = streamer.generate_stream()

    total_records = 0
    gap_records   = 0

    for rec in stream:
        total_records += 1
        if rec["data_valid"] == 0:
            gap_records += 1

        if total_records % 50_000 == 0:
            print(f"  Processed {total_records:,} records ({gap_records:,} imputed gaps so far)...")

        sid = rec["stop_id"]
        if sid not in ALL_STOPS or rec["data_valid"] != 1:
            continue

        day_type = "Weekend" if rec["day_of_week"] >= 5.0 else "Weekday"
        h        = int(rec["hour"])
        _eda[sid][day_type][h][0] += rec["boardings"]
        _eda[sid][day_type][h][1] += 1

    # ------------------------------------------------------------------
    # Print reproducible availability statistics
    # ------------------------------------------------------------------
    real_records = total_records - gap_records
    avail_pct    = 100.0 * real_records / total_records if total_records > 0 else 0.0

    print(f"\nStream summary:")
    print(f"  Total records (real + imputed) : {total_records:,}")
    print(f"  Real sensor records            : {real_records:,}")
    print(f"  Imputed gap records            : {gap_records:,}")
    print(f"  Empirical availability         : {avail_pct:.2f}%")

    # ------------------------------------------------------------------
    # Phase 4: EDA plots, one per stop, weekday vs weekend overlay
    # ------------------------------------------------------------------
    print("\n--- Phase 4: EDA Plot Generation ---")

    for stop_id, (stop_name, stop_colour) in ALL_STOPS.items():
        print(f"  Plotting: {stop_name} (stop {stop_id}) ...")

        rows = []
        for day_type in ("Weekday", "Weekend"):
            for h in range(24):
                total_val, count = _eda[stop_id][day_type][h]
                mean_val = (total_val / count) if count > 0 else 0.0
                rows.append({
                    "Day Type":          day_type,
                    "Hour of Day":       h,
                    "Mean Boardings":    mean_val,
                })

        df_plot = pd.DataFrame(rows)

        fig, ax = plt.subplots(figsize=(11, 5))
        sns.lineplot(
            data=df_plot,
            x="Hour of Day",
            y="Mean Boardings",
            hue="Day Type",
            style="Day Type",
            palette={"Weekday": "#1f77b4", "Weekend": "#d62728"},
            linewidth=2.5,
            markers=True,
            markevery=2,
            ax=ax,
        )
        ax.set_title(f"{stop_name}  |  Stop ID: {stop_id}", fontsize=13, weight="bold", pad=12)
        ax.set_xlabel("Hour of Day (24 h)", fontsize=11)
        ax.set_ylabel("Mean 5-min Boarding Count", fontsize=11)
        ax.set_xticks(range(24))
        ax.grid(True, linestyle=":", alpha=0.6)
        fig.tight_layout()

        out_path = plots_out_dir / f"eda_boardings_stop_{stop_id}.png"
        fig.savefig(out_path, dpi=200)
        plt.close(fig)
        print(f"    Saved: {out_path.relative_to(base_dir)}")

    print("\nPhase 4 complete. All EDA plots saved to 'eda_plots/'.")
    print("\nRole A pipeline complete.")


# ===========================================================================
# MODULE 4, Downstream CapyMOA Handle 
# ===========================================================================

# Per-stop regression schema cache, built once, reused across calls
_STOP_SCHEMAS: dict[str, "Schema"] = {}

# Feature names in the order they appear in every x-vector.
# boardings is listed last because Schema.from_custom() requires the
# target to be the final entry when the task is regression.
_FEATURE_NAMES = [
    "hour",
    "minute",
    "day_of_week",
    "alightings",
    "occupancy_load",
    "data_valid",
    "boardings",      # <-- target (y); must be last in the list
]


def _get_stop_schema(stop_id: str) -> "Schema":
    """Return (and cache) a regression Schema for the given stop.

    Schema.from_custom() contract (CapyMOA 0.13):
      - `features` must include the target name
      - target is numeric (no entry in `categories`) → regression task
    """
    if stop_id not in _STOP_SCHEMAS:
        _STOP_SCHEMAS[stop_id] = Schema.from_custom(
            features=_FEATURE_NAMES,
            target="boardings",
            name=f"SUNT-stop-{stop_id}",
        )
    return _STOP_SCHEMAS[stop_id]


def get_stop_stream(stop_id: str):
    """Yield CapyMOA RegressionInstance objects for a single stop.

    This is the primary downstream interface for Roles C and D.

    Each instance encodes:
        x  = [hour, minute, day_of_week, alightings, occupancy_load, data_valid]
        y  = boardings  (the regression target)

    No weights are set. Weighting policy (if any) is a modelling decision
    for Roles C and D.

    Parameters
    ----------
    stop_id : str
        One of the 10 production stop IDs defined in ALL_STOPS.

    Yields
    ------
    RegressionInstance
        A native CapyMOA 0.13 object ready for prequential (test-then-train)
        evaluation loops.

    Raises
    ------
    RuntimeError
        If CapyMOA is not available in the current environment.
    ValueError
        If stop_id is not one of the 10 production stops.

    Example usage (Roles C / D)
    ----------------------------
    from process_sunt import get_stop_stream, ALL_STOPS
    from capymoa.regressor import AdaptiveRandomForestRegressor

    for stop_id in ALL_STOPS:
        model  = AdaptiveRandomForestRegressor(schema=get_stop_schema(stop_id))
        for instance in get_stop_stream(stop_id):
            prediction = model.predict(instance)
            model.train(instance)
    """
    if not HAS_CAPYMOA:
        raise RuntimeError(
            "CapyMOA is not available. Install Java 17, then: "
            "pip install capymoa==0.13.0"
        )

    if stop_id not in ALL_STOPS:
        raise ValueError(
            f"Unknown stop_id '{stop_id}'. "
            f"Valid IDs: {list(ALL_STOPS.keys())}"
        )

    schema = _get_stop_schema(stop_id)

    for rec in IncrementalTransitStreamer().generate_stream():
        if rec["stop_id"] != stop_id:
            continue

        # 6 input features only; boardings is the regression target (y) and must
        # NOT appear in x (the schema has 6 attributes, target excluded). Including
        # it here would leak the answer into the model's inputs.
        x = np.array([
            rec["hour"],
            rec["minute"],
            rec["day_of_week"],
            rec["alightings"],
            rec["occupancy_load"],
            float(rec["data_valid"]),
        ], dtype=np.float64)

        yield RegressionInstance.from_array(
            schema=schema,
            x=x,
            y_value=np.float64(rec["boardings"]),
        )


def get_all_stop_streams() -> dict:
    """Return a dict mapping each stop_id to its generator.

    Convenience wrapper so Roles C/D can iterate all stops without
    managing stop IDs manually.

    Returns
    -------
    dict[str, generator]
        Keys are stop IDs; values are generators from get_stop_stream().

    Example
    -------
    from process_sunt import get_all_stop_streams

    streams = get_all_stop_streams()
    for stop_id, stream in streams.items():
        for instance in stream:
            ...   # prequential loop
    """
    return {sid: get_stop_stream(sid) for sid in ALL_STOPS}


# ---------------------------------------------------------------------------
# Standalone confirmation message (only when run as main script)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(
        "\nCapyMOA downstream handle ready.\n"
        "  - get_stop_stream(stop_id)  -> single-stop RegressionInstance generator\n"
        "  - get_all_stop_streams()    -> dict of all 10 stop generators\n"
        "  - ALL_STOPS                 -> dict of stop metadata\n"
    )
