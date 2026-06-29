# Role D - Framing 3: scheduled-service vs demand alignment

## What this answers

Role F raised the right framing: there are **two different things** we
can look for, and they should be told apart in the report.

1. **Schedule (mis)alignment** - does the bus *timetable* match where demand
   actually peaks? (a planning/scheduling question)
2. **Concept drift in demand itself** - weather/holiday effects on the boarding
   boundary (Framings 1 and 2 already cover this).

This module adds the **supply side** (1). It was previously missing: we only
had the boarding (demand) signal and an assumed official window (06:00-09:00 /
17:00-20:00). Now we use the real GTFS timetable (`stop_times.txt`) instead of
that assumption, which removes the "we assumed fixed windows" weakness Role F
flagged.

## Method (brief)

1. Parse GTFS `stop_times.txt` (filtered to our 10 stops; the file is ~88 MB
   for the whole network), `trips.txt` (trip -> service_id), `calendar.txt`
   (service_id -> weekday/Saturday flags). Arrival times > 24:00:00 wrap mod
   1440.
2. Build a **scheduled-arrival profile** per stop per day-type: count scheduled
   arrivals in each 5-minute bin on a representative weekday / Saturday.
3. Extract the **scheduled peak start** with the *same rule* as the online
   demand detector (`src/peaks.py`): smoothed arrivals exceed `mean + K*std`,
   sustained for `SCHED_MIN_SUSTAIN` bins, inside the AM/PM window.
4. Compare to the data-driven **demand peak** (Framing 1) -> `gap = demand -
   scheduled` (minutes). Positive gap = demand peaks later than service is
   concentrated.

Files: `src/schedule_alignment.py`, `scripts/04_schedule_alignment.py`.
Params in `config.py`: `SCHED_THRESH_K=0.5`, `SCHED_MIN_SUSTAIN=3`,
`SCHED_SMOOTH_BINS=3`. Output: `outputs/schedule_alignment.csv`,
`figures/schedule_<stop>.png`.

Note on the streaming requirement: the timetable is **static**, so this
alignment is a *descriptive supply-vs-demand layer, not an online-ML task*. The
streaming requirement stays satisfied by Framings 1 and 2. Also, `stop_times`
is the *scheduled* timetable, not realized AVL arrivals (those are not in the
10-stop subset), so we phrase findings as "scheduled service vs demand".

## Real result (ran on Kaggle over the real data: 21,840 x 10 boarding
intervals; 21,554 scheduled arrivals at the 10 stops)

**Headline - weekday morning (AM), where the demand peak is well defined:**

| Stop | Scheduled peak | Demand peak | Gap |
|---|---|---|---|
| Lapa Station | 05:50 | 06:09 | +19 min |
| Salvador Bus Station | 05:45 | 06:20 | +35 min |
| Ferry terminal | 06:00 | 06:46 | +46 min |
| Castro Alves Theater | 06:30 | 07:21 | +51 min |
| Lacerda Elevator | 06:25 | 07:27 | +63 min |

**Consistent story:** across commuter/hub stops the timetable front-loads
morning service roughly **20-60 minutes before** real boarding demand peaks.
Actionable: shift the first reinforcement runs ~20-40 min later at these stops
so buses arrive with demand, not ahead of it. This is exactly the kind of
concrete, operator-actionable result the lecturer asked for.

## Honest caveats (write these in the report)

- **PM gaps are unreliable.** Afternoon service is a long plateau (roughly
  15:00-20:00), so "first threshold crossing" fires near the window open
  (~15:00) and inflates PM gaps (+100 to +250). Report PM with caution or use a
  density-centre measure; the **AM** comparison is the trustworthy one because
  both demand and supply have a sharp morning ramp.
- **UFBA AM demand = 10:30** is a detector artifact (university mid-morning),
  so its +275 gap is not meaningful; exclude or annotate.
- Several event/leisure stops (Itapua, Arena, Barradao) have **no clear demand
  peak** in this 3-month window, so the gap is undefined there - itself a
  finding (these stops are event-driven, not commuter-driven).
- Weekend scheduled peak uses **Saturday** service as the proxy; demand weekend
  mixes Sat+Sun.
- The standalone Kaggle run streamed ~76 days without gap imputation; the local
  `scripts/04_schedule_alignment.py` reproduces the same logic on Role B's
  feature table (`process_sunt` gap-imputed), so small differences are expected.

## Reproduce

Local (no Java/CapyMOA needed - pure pandas/numpy):
```
python scripts/01_download_data.py        # fetches gtfs/stop_times.txt (~88 MB)
python scripts/04_schedule_alignment.py   # -> outputs/ + figures/
```
Cloud: Kaggle notebook `necmikural/concept-drifters-schedule-alignment`
(self-contained: downloads from Hugging Face, runs the same logic).
