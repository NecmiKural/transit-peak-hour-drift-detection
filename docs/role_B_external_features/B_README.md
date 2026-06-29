# Role B, External Data \& Streaming Features

## COMPX523 Assignment 3 | Team: Concept Drifters

### Topic 4: Peak-Hour Boundary Detection, *When does rush hour really start?*

\---

## Overview

`role\_b\_features.py` is the external data and feature engineering script for Role B. It:

1. Fetches hourly weather data (precipitation + temperature) for Salvador from the Open-Meteo Historical Archive API, free, no API key required
2. Builds the Brazilian national holiday calendar for the study window (Mar–May 2024)
3. Downloads the SUNT 10-stop 5-minute boarding data from Hugging Face (`labiaufba/SSA\_StopBusTimeSeries\_5`)
4. Joins weather and holiday data onto the boarding stream, aligning all timestamps to Salvador local time (UTC-3)
5. Builds a full set of streaming-safe features, time-of-day, cyclic encodings, lag features, rolling statistics, and rain flags, with no lookahead (past data only)
6. Outputs a single ready-to-use feature table (`features\_stream.csv`) for Roles C and D

\---

## Installation

```bash
pip install requests pandas numpy huggingface\_hub
```

No CapyMOA or Java required to run Role B. The output CSV is framework-agnostic and works with any downstream model.

\---

## Usage

### Option 1, Google Colab (recommended)

1. Open [colab.research.google.com](https://colab.research.google.com) and create a new notebook
2. Paste the full contents of `role\_b\_features.py` into a single cell
3. Run the cell, it installs dependencies, downloads data, and saves output files automatically
4. Download the output files when prompted

### Option 2, Local

Place `role\_b\_features.py` in your working directory and run:

```bash
python role\_b\_features.py
```

On first run, weather data is fetched from Open-Meteo and boarding data is downloaded from Hugging Face into `data/`. Subsequent runs load from local cache and skip the download.

### Expected terminal output

```
✓ Setup done

\[1/5] Fetching weather from Open-Meteo ...
  ✓ 2208 hourly rows. Preview:
             timestamp  precipitation\_mm  temperature\_2m
  2024-03-01 00:00:00               0.0            26.3
  ...

\[2/5] Building holiday calendar ...
  ✓ 3 holidays:
         date     holiday\_name  is\_holiday
   2024-03-29      Good Friday        True
   2024-04-21       Tiradentes        True
   2024-05-01       Labour Day        True

\[3/5] Loading SUNT 5-min boarding data ...
  ✓ 218,400 rows × 10 stops

\[4/5] Joining weather + holidays ...
  ✓ Merged shape: (218400, 7)

\[5/5] Building streaming features ...
  ✓ Shape: (218400, 26)

── Day-type distribution ──
weekday    151200
weekend     60000
holiday      7200

── Rain distribution ──
none        160080
light        55320
moderate      2760
heavy          240

── Missing values ──
  None ✓

🎉 Role B complete!
```

\---

## External Data Sources

### Weather, Open-Meteo Historical Archive API

|Property|Value|
|-|-|
|Source|archive-api.open-meteo.com|
|Variables|Hourly precipitation (mm), temperature at 2m (°C)|
|Location|Salvador, Bahia (lat -12.9714, lon -38.5014)|
|Timezone|America/Bahia (UTC-3, no DST)|
|Resolution|Hourly → forward-filled to 5-min to match SUNT|
|Window|1 March 2024, 31 May 2024|
|Total rows|2,208 hourly records|
|Missing values|None|
|API key required|No, free, open access|

### Holidays, Brazilian National Calendar

|Date|Holiday|Type|
|-|-|-|
|29 March 2024|Good Friday (Sexta-feira Santa)|National|
|21 April 2024|Tiradentes|National|
|1 May 2024|Labour Day (Dia do Trabalho)|National|

No Bahia state holidays fall within the Mar–May 2024 window. Dates are hardcoded from the official Brazilian national holiday calendar, no API needed.

\---

## Output Files

### `features\_stream.csv`, PRIMARY OUTPUT (41.2 MB)

|Property|Value|
|-|-|
|Shape|218,400 rows × 26 columns|
|Date range|2024-03-01 05:00:00 → 2024-05-31 00:55:00|
|Stops|10 (all SUNT stops in the subset)|
|Interval|5 minutes|
|Missing values|None|

**Important:** `stop\_id` is stored as `int64`. Filter rows with:

```python
df\[df\['stop\_id'] == 43768720]   # correct, integer
df\[df\['stop\_id'] == '43768720'] # wrong, string will return nothing
```

#### Full column list

|Column|Type|Description|
|-|-|-|
|`timestamp`|str|5-min interval timestamp (UTC-3 local)|
|`stop\_id`|int64|GTFS stop identifier|
|`boardings`|int64|Passenger boardings in that 5-min interval|
|`precipitation\_mm`|float64|Hourly rainfall forward-filled to 5-min|
|`temperature\_2m`|float64|Air temperature at 2m height (°C)|
|`is\_holiday`|bool|True on Good Friday, Tiradentes, Labour Day|
|`holiday\_name`|str|Holiday name or empty string|
|`hour\_of\_day`|float64|Hour + minute/60, e.g. 6.5 = 06:30|
|`minute\_of\_hour`|int64|0, 5, 10 … 55|
|`sin\_hour`|float64|Cyclic sine encoding of hour|
|`cos\_hour`|float64|Cyclic cosine encoding of hour (use with sin\_hour)|
|`day\_of\_week`|int64|0=Monday … 6=Sunday|
|`is\_weekend`|bool|True for Saturday and Sunday|
|`week\_of\_year`|int64|ISO week number|
|`day\_type`|str|`'weekday'` \| `'weekend'` \| `'holiday'`|
|`boarding\_lag\_1`|float64|Boardings 5 min ago|
|`boarding\_lag\_2`|float64|Boardings 10 min ago|
|`boarding\_lag\_3`|float64|Boardings 15 min ago|
|`boarding\_lag\_6`|float64|Boardings 30 min ago|
|`boarding\_lag\_12`|float64|Boardings 60 min ago|
|`rolling\_mean\_6`|float64|Rolling mean over last 30 min (6 intervals)|
|`rolling\_std\_6`|float64|Rolling std over last 30 min|
|`rolling\_mean\_12`|float64|Rolling mean over last 60 min (12 intervals)|
|`rolling\_std\_12`|float64|Rolling std over last 60 min|
|`is\_raining`|bool|True when precipitation\_mm > 0.1|
|`rain\_intensity`|str|`'none'` \| `'light'` \| `'moderate'` \| `'heavy'`|

### `weather\_salvador.csv` (62.6 KB)

Hourly weather for Salvador across the study window. 2,208 rows, 3 columns: `timestamp`, `precipitation\_mm`, `temperature\_2m`. Cached locally after first fetch.

### `holidays\_2024.csv` (111 B)

Three-row table of national holidays: `date`, `holiday\_name`, `is\_holiday`.

\---

## Output Structure

```
role\_b\_features.py
data/
    features\_stream.csv       # PRIMARY, hand to Roles C and D
    weather\_salvador.csv      # hourly weather cache
    holidays\_2024.csv         # holiday calendar
    boarding\_5min\_wide.csv    # SUNT boarding cache (wide format)
```

Add the following to `.gitignore` to avoid pushing large data files:

```
data/
```

\---

## The 10 Production Stops

|Stop ID|Name|Character|
|-|-|-|
|43768720|Lapa Station Hub|Major transfer hub, bimodal peak pattern|
|44783654|UFBA University Gate|Weekday commuter, drops on weekends|
|230565994|Itapua Beach|Leisure, weekend surge|
|125960550|Arena Fonte Nova Stadium|Event-driven, spikes on match days|
|45833547|Barradao Stadium|Event-driven, spikes on match days|
|44784438|Ferry Terminal|Mixed, tourist + commuter|
|47568123|Shopping Mall|Retail hours, afternoon/evening peak|
|44072192|Castro Alves Theater|Evening and cultural events|
|258781031|Salvador Bus Terminal|Intercity, spread across all hours|
|44783914|Lacerda Elevator|Tourist, daytime only|

\---

## Downstream Integration (Roles C and D)

Place `features\_stream.csv` alongside your script and load it directly. No imports from Role B's script are needed.

```python
import pandas as pd

# Load Role B feature table
df = pd.read\_csv('features\_stream.csv', parse\_dates=\['timestamp'])

# Filter to a single stop (stop\_id is integer)
df\_lapa = df\[df\['stop\_id'] == 43768720]

# Stream rows in time order for prequential evaluation
df\_sorted = df.sort\_values(\['timestamp', 'stop\_id']).reset\_index(drop=True)

FEATURE\_COLS = \[
    'hour\_of\_day', 'sin\_hour', 'cos\_hour', 'day\_of\_week',
    'is\_weekend', 'is\_holiday', 'boarding\_lag\_1', 'boarding\_lag\_2',
    'boarding\_lag\_3', 'boarding\_lag\_6', 'boarding\_lag\_12',
    'rolling\_mean\_6', 'rolling\_std\_6', 'rolling\_mean\_12', 'rolling\_std\_12',
    'precipitation\_mm', 'temperature\_2m', 'is\_raining',
]

for \_, row in df\_sorted.iterrows():
    x = row\[FEATURE\_COLS].values.astype(float)
    y = row\['boardings']   # regression target
    # prediction = model.predict(instance)
    # model.train(instance)
```

### Relationship with Role A

Role A's `process\_sunt.py` exposes `get\_stop\_stream(stop\_id)` which yields CapyMOA `RegressionInstance` objects with 6 features (hour, minute, day\_of\_week, alightings, occupancy\_load, data\_valid). Role B's `features\_stream.csv` is the richer input, it adds weather, holidays, lag features, rolling statistics, and rain flags that Role A's stream does not include.

**Recommendation:** Use `features\_stream.csv` as the primary input. If alightings and occupancy\_load are also needed, merge them in from Role A's output on `timestamp + stop\_id`.

\---

## Design Notes

**No lookahead, streaming-safe features only**
All lag and rolling features are computed with `shift(1)` before any rolling operation, ensuring the model never sees future data. This is consistent with the online/prequential constraint.

**Timezone alignment**
All timestamps are in Salvador local time (UTC-3, no DST). The Open-Meteo API returns data in `America/Bahia` timezone. Any timezone metadata is stripped to tz-naive local time before the join to avoid misalignment.

**Weather resolution**
Open-Meteo provides hourly data. It is joined to the 5-min stream by flooring each 5-min timestamp to the nearest hour and forward-filling. No interpolation is applied, forward-fill is the safest choice for a streaming context.

**Cyclic hour encoding**
`sin\_hour` and `cos\_hour` encode the hour of day as a point on a unit circle. This ensures the model understands that 23:55 and 00:05 are close in time, which raw hour integers do not capture.

**Rain intensity bins**
Standard meteorological thresholds: none (0–0.1 mm/hr), light (0.1–2.5), moderate (2.5–7.6), heavy (>7.6).

**Reproducibility**
The script is fully reproducible. Weather data is cached after first fetch. The Hugging Face boarding data is cached locally. Re-running the script produces identical output.

\---

## Completion Status

|Task|Status|
|-|-|
|Weather data fetched from Open-Meteo (2,208 rows, 0 missing)|✓ Done|
|Holiday calendar built, 3 national holidays|✓ Done|
|SUNT 5-min boarding data downloaded from Hugging Face|✓ Done|
|Weather joined to 5-min stream (forward-fill, UTC-3 aligned)|✓ Done|
|Holiday flags joined on calendar date|✓ Done|
|Streaming features built, 26 columns, no lookahead, 0 missing|✓ Done|
|features\_stream.csv saved (41.2 MB, 218,400 rows)|✓ Done|
|All 3 output files verified, shapes, date ranges, distributions|✓ Done|
|Handover notes prepared for Roles C, D, and F|✓ Done|

\---



