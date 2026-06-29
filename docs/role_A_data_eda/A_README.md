# Role A, Data Ingestion, Gap Imputation & EDA Pipeline
## COMPX523 Assignment 3 | Team: Concept Drifters
### Topic 4: Peak-Hour Boundary Detection, *When does rush hour really start?*

---

## Overview

`process_sunt.py` is the upstream data engineering script for Role A. It:

1. Downloads the 10-stop SUNT 5-minute subset from Hugging Face (`labiaufba/SSA_StopBusTimeSeries_5`)
2. Streams all three CSV files incrementally through a micro-chunk generator (O(1) memory, no batch penalty)
3. Imputes missing 5-minute intervals on-the-fly using an incremental cyclic EWMA baseline
4. Produces one EDA plot per stop (weekday vs weekend hourly boarding profile)
5. Exposes per-stop `RegressionInstance` generators for Roles C and D via `get_stop_stream()` and `get_all_stop_streams()`

---

## Installation

### Python packages

```bash
pip install huggingface_hub pyarrow pandas matplotlib seaborn
```

### CapyMOA (required for downstream handle, Roles C and D)

CapyMOA requires **Java 17**. Install it first, then:

```bash
pip install capymoa==0.13.0
```

The script runs without CapyMOA (Phases 1–4 complete normally). The downstream handle functions raise a `RuntimeError` if CapyMOA is absent.

---

## Usage

Place `process_sunt.py` in your working directory and run:

```bash
python -u process_sunt.py
```

On first run, the three CSVs are downloaded from Hugging Face into `data_cache/`. Subsequent runs detect the cached files and skip the download.

### Expected terminal output

```
Checking Python environment dependencies...
Dependency check complete.

CapyMOA 0.13.0 bound successfully.
--- Phase 1: Data Ingestion ---
  Using cached file: boarding_03-05_2024.csv
  Using cached file: landing_03-05_2024.csv
  Using cached file: loader_03-05_2024.csv
Phase 1 complete. All CSV assets located.

--- Phase 3: Online EDA Accumulation ---
--- Phase 2: Streaming ---
  Processed 50,000 records (... imputed gaps so far)...
  ...

Stream summary:
  Total records (real + imputed) : 261,600
  Real sensor records            : 218,400
  Imputed gap records            : 43,200
  Empirical availability         : 83.49%

--- Phase 4: EDA Plot Generation ---
  Plotting: Lapa Station Hub (stop 43768720) ...
    Saved: eda_plots\eda_boardings_stop_43768720.png
  ...

Phase 4 complete. All EDA plots saved to 'eda_plots/'.

Role A pipeline complete.

CapyMOA downstream handle ready.
  - get_stop_stream(stop_id)  -> single-stop RegressionInstance generator
  - get_all_stop_streams()    -> dict of all 10 stop generators
  - ALL_STOPS                 -> dict of stop metadata
```

---

## Dataset

| Property | Value |
|---|---|
| Source | Hugging Face: `labiaufba/SSA_StopBusTimeSeries_5` |
| Files | `boarding_03-05_2024.csv`, `landing_03-05_2024.csv`, `loader_03-05_2024.csv` |
| Format | Wide, rows = 5-min timestamps, columns = 10 stop IDs |
| Window | 1 March 2024 00:00, 31 May 2024 23:55 (Salvador, UTC−3) |
| Total stream elements | 261,600 (10 stops × 26,160 intervals) |
| Real sensor records | 218,400 (83.49% empirical availability) |
| Imputed gap records | 43,200 (16.51%) |

### The 10 production stops

| Stop ID | Location |
|---|---|
| 43768720 | Lapa Station Hub |
| 44783654 | UFBA University Gate |
| 230565994 | Itapua Beach Leisure |
| 125960550 | Arena Fonte Nova Stadium |
| 45833547 | Barradao Stadium |
| 44784438 | Ferry Terminal |
| 47568123 | Shopping Mall Corridor |
| 44072192 | Castro Alves Theater |
| 258781031 | Salvador Bus Station Terminal |
| 44783914 | Lacerda Elevator Tourist |

---

## Output structure

```
process_sunt.py
data_cache/               # downloaded CSVs (auto-created; do not commit)
    boarding_03-05_2024.csv
    landing_03-05_2024.csv
    loader_03-05_2024.csv
eda_plots/                # 10 PNG figures (auto-created)
    eda_boardings_stop_43768720.png
    eda_boardings_stop_44783654.png
    ...
```

Add the following to `.gitignore`:

```
data_cache/
eda_plots/
```

---

## Downstream integration (Roles C and D)

Place your script alongside `process_sunt.py`. Import directly, no data loading or cleaning logic needs to be duplicated.

### Feature vector layout

Every `RegressionInstance` carries:

| Index | Feature | Type |
|---|---|---|
| 0 | `hour` | float [0–23] |
| 1 | `minute` | float [0, 5, 10 … 55] |
| 2 | `day_of_week` | float [0=Mon … 6=Sun] |
| 3 | `alightings` | float ≥ 0 |
| 4 | `occupancy_load` | float ≥ 0 |
| 5 | `data_valid` | float {1.0 = real, 0.0 = imputed} |
| 6 | `boardings` | float ≥ 0 ← **regression target (y)** |

No peak labels and no instance weights are set at this layer. Peak boundary detection is performed by `src/peaks.py` (Role D). Weighting decisions belong to Roles C and D.

### Single-stop stream

```python
from process_sunt import get_stop_stream, ALL_STOPS
from capymoa.regressor import AdaptiveRandomForestRegressor

stop_id = "44783654"   # UFBA University Gate
model   = AdaptiveRandomForestRegressor(schema=...)

for instance in get_stop_stream(stop_id):
    prediction = model.predict(instance)
    model.train(instance)   # test-then-train (prequential)
```

### All 10 stops

```python
from process_sunt import get_all_stop_streams, ALL_STOPS

streams = get_all_stop_streams()   # dict: stop_id -> generator
for stop_id, stream in streams.items():
    for instance in stream:
        ...
```

### Public API surface

| Symbol | Type | Description |
|---|---|---|
| `get_stop_stream(stop_id)` | generator | Per-stop `RegressionInstance` stream |
| `get_all_stop_streams()` | dict | All 10 stop generators keyed by stop ID |
| `ALL_STOPS` | dict | `{stop_id: (name, colour)}` metadata |

---

## Design notes

**Incremental processing (no batch penalty)**
Data is processed in 1,000-row micro-chunks via `pd.read_csv(chunksize=1000)`. No full CSV is ever loaded into RAM.

**Gap imputation**
Missing 5-minute slots are detected by comparing each incoming timestamp against the last emitted timestamp. Synthetic records are injected using a per-(time-of-day, stop) EWMA baseline (α = 0.05) updated incrementally from previously seen values. Imputed records carry `data_valid = 0` so downstream models can filter or weight them independently.

**CSV desync guard**
Row counts across the three CSV files are checked per chunk. A mismatch raises a `RuntimeError` immediately rather than silently pairing wrong rows through `zip()`.

**Timestamp format guard**
Timestamp parsing uses an explicit format string (`%Y-%m-%d %H:%M:%S`). A format mismatch raises a `ValueError` with a clear diagnostic message rather than silently producing `NaT`.

**Reproducibility**
Global random seed is fixed at `np.random.seed(42)`. All outputs are fully reproducible from the cached CSV files alone.
