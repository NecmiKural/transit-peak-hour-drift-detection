# Transit Peak-Hour Boundary Detection and Drift

**When does rush hour really start?** An online analysis of bus boarding
demand in Salvador, Brazil, that detects the true start and end of the morning
and evening peaks per stop, then checks whether those boundaries drift over time
or shift across weekday / weekend / holiday / rainy days. Framed as a streaming
change-detection problem on [CapyMOA](https://capymoa.org/) / MOA.

Data: three months (March to May 2024) of historical 5-minute estimated boarding counts for 10 Salvador bus stops (SUNT, CC BY 4.0), replayed as a stream.

Six-person COMPX523 group project, shared here as a portfolio sample with the
team's agreement. **My part: Role D (change-point and drift):** the adaptive
boundary detector, the ADWIN and Page-Hinkley drift tests and the schedule
alignment. See [Team](#team) for full credit and [`report/`](report/) for the
final paper and slides.

## The question and why it matters

Operators schedule reinforcement service against fixed official peak windows
(typically 06:00 to 09:00 and 17:00 to 20:00), which assume demand is
stationary. Real per-stop demand may peak earlier or later, and may shift over
the season. A misaligned timetable means buses arrive after the demand has
already queued, which cascades into downstream congestion. We treat the boarding
feed as an infinite stream and ask three questions:

1. **Boundary detection.** Where does each stop's real peak begin and end,
   detected online, and how far is that from the official window?
2. **Drift (the streaming core).** Do those boundaries, or an online model's
   prediction error, drift over the three-month window? Tested with CapyMOA
   ADWIN and Page-Hinkley.
3. **Schedule alignment.** From the GTFS timetable, how large is the gap
   between scheduled service peaks and the detected demand peak?

## Dataset

The assignment's 10-stop subset of the
[`labiaufba/SSA_StopBusTimeSeries_5`](https://huggingface.co/datasets/labiaufba/SSA_StopBusTimeSeries_5)
Hugging Face dataset: 5-minute boarding / landing / occupancy aggregations for
**March to May 2024**, around 1 MB per CSV. The counts are historical estimates
that the dataset's authors derived from AVL, AFC and GTFS records, not live
feeds; this project replays them in time order as a stream. The dataset comes
from the [SUNT](https://github.com/LabIA-UFBA/SUNT) project, licensed CC BY 4.0.
Re-downloadable with `scripts/01_download_data.py` (data itself is gitignored,
not redistributed).

| Stop ID | Location | Character |
|---|---|---|
| 44783654 | UFBA (Federal University of Bahia) | students/staff, strong weekday AM signal (in alightings) |
| 43768720 | Lapa Station | main terminal, commuter hub, cleanest peak |
| 230565994 | Itapuã Lighthouse Beach | leisure, higher on weekends/holidays |
| 125960550 | Arena Fonte Nova | sport/cultural events, near-zero baseline |
| 45833547 | Manoel Barradas Stadium | game-day spikes only |
| 44784438 | Ferry Boat terminal | intercity / cross-bay |
| 47568123 | Major shopping mall | all-day commercial |
| 44072192 | Castro Alves Theater | evening / event peaks |
| 258781031 | Salvador Bus Station | central intercity hub |
| 44783914 | Lacerda Elevator | tourist / commercial district |

## Headline results

**Detected demand boundaries vs the official window** (online adaptive-threshold
detector with CapyMOA ADWIN; from the Kaggle run recorded in
`outputs/D_drift_findings.md`. `outputs/ampm_summary_real.csv` is a local
development run without Java, using the fallback detector, so its numbers
differ slightly):

| Stop | Period | Detected start (weekday) | Official | Weekend shift |
|---|---|---|---|---|
| Lapa Station | AM | **06:10** | 06:00 | +10 min |
| Salvador Bus Station | PM | **17:05** | 17:00 | +48 min |
| Lacerda Elevator | PM | 17:06 | 17:00 | +80 min |
| Shopping mall | PM | 15:57 | 17:00 | **+193 min** |
| Castro Alves Theater | PM | 17:21 | 17:00 | +89 min |

**The streaming finding: no temporal concept drift in this window.** CapyMOA
ADWIN on the per-day boundary series and on the per-day model RMSE both flag
**zero drift days for every stop analysed** (the five stops above for the
boundaries; eight stops for the model error, without Arena Fonte Nova and
Manoel Barradas Stadium, see `outputs/role_d_concept_drift.csv`). The real, actionable variation is
*structural* (weekday vs weekend vs holiday, and stop type), not slow temporal
drift. A methodological caveat we document honestly: per-instance ADWIN on the
model error fires constantly (55 to 186 times per stop), but only because it
tracks the within-day demand cycle, so the per-day RMSE series is the correct
granularity.

**Model comparison (Framing 1, regression).** At 5-minute resolution the series
is spiky and low-count, so a naive previous-interval persistence baseline is hard
to beat (mean RMSE around 1.86) and the online CapyMOA ARF regressor sits higher.
We frame this honestly in the report: the streaming model's value here is
adaptivity, not raw accuracy.

A reliability gate (`config.MIN_DAILY_DEMAND` / `MIN_PEAK_DAYS`) flags which of
the 20 (stop, period) series carry enough demand to have a real peak; 10 of 20
are reliable, and the headline figures use only those. Full discussion in
`docs/role_E_evaluation_viz/README.md` and `outputs/D_drift_findings.md`.

## Approach

Three framings, all single-pass and online where it counts:

- **Adaptive boundary detection** (`src/peaks.py`): an EWMA off-peak baseline
  with a `mean + K*std` threshold and a sustain rule, inside morning and evening
  search windows, producing a per-day peak start and end.
- **Drift detection** (`src/drift.py`, `src/drift_analysis.py`): CapyMOA ADWIN
  and Page-Hinkley over the daily boundary series and over an online regressor's
  error, segmented by weekday / weekend / holiday and correlated with rainfall.
- **Online demand model** (`src/pipeline.py`): a CapyMOA Adaptive Random Forest
  regressor evaluated prequentially (test-then-train) against persistence and
  fixed-window baselines.
- **Schedule alignment** (`src/schedule_alignment.py`): pure pandas, builds a
  per-stop scheduled-arrival profile from GTFS `stop_times.txt` and reports the
  gap to the detected demand peak.

External signals (`external/`): Open-Meteo weather for Salvador and the
Brazil/Bahia holiday calendar for the window, merged with no look-ahead.

## Repository layout

```
transit-peak-hour-drift-detection/
├── README.md                 ← this file
├── config.py                 ← stops, paths, peak/drift params, seed
├── requirements.txt
├── CHANGES.md                ← dataset-modification log (required by brief)
├── run_all.py                ← one-command pipeline driver
├── process_sunt.py           ← data layer: ingestion + per-stop streams
├── Evaluation.ipynb          ← evaluation / visualization notebook
├── src/                      ← peaks, drift, drift_analysis, pipeline, schedule_alignment, features
├── scripts/                  ← 01 download · 02 build features · 03 drift · 04 schedule · helpers
├── external/                 ← Open-Meteo weather + Bahia holidays
├── figures/                  ← EDA + result figures (role_E_polished/ by Role E, Saurabh Jyala)
├── outputs/                  ← result CSVs + D_drift_findings.md
├── report/                   ← final paper (PDF) + slides (PDF)
└── docs/                     ← per-role method notes and handovers
```

> **Data not included.** The Hugging Face boarding CSVs and the ~88 MB GTFS
> `stop_times.txt` are re-downloadable via `scripts/01_download_data.py`; they
> are gitignored, not redistributed.

## Run

```bash
cd transit-peak-hour-drift-detection
python3.11 -m venv .venv          # CapyMOA needs Python >= 3.10
source .venv/bin/activate
pip install -r requirements.txt

export JAVA_HOME=/path/to/openjdk-17   # CapyMOA needs Java 17

python scripts/01_download_data.py     # pull HF CSVs + GTFS into data/
python scripts/02_build_features.py    # weather + holidays + lag features
python scripts/03_drift_analysis.py    # boundary detection + ADWIN drift
python scripts/04_schedule_alignment.py
```

The canonical CapyMOA ADWIN run (boundaries and model error) is
`scripts/kaggle_drift_run.py`; the offline path falls back gracefully without
Java for development.

## Team

A six-person project, with equal credit. Roles, in CRediT terms:

| Role | Member | Contribution |
|---|---|---|
| A. Data & EDA | Van Deiv Nayak | Data curation, the canonical loader, per-stop EDA |
| B. External data & features | Aryan Chauhan | Weather/holiday merge, streaming feature builder |
| C. Streaming modeling | Hans Kristian Lomboy | Online ARF regressor, prequential baselines |
| D. Change-point / drift | Necmi Kural | Adaptive boundary detector, ADWIN/PH drift, schedule alignment |
| E. Evaluation, viz & repro | Saurabh Jyala | Evaluation notebook, polished figures, reliability gate |
| F. Report & presentation / PM | Eugenio Di Giuseppe | Report assembly, slides, project management |


## Tech

Python · CapyMOA / MOA (JPype, OpenJDK 17) · pandas · NumPy · Open-Meteo · GTFS.

---
*University coursework (COMPX523, group project). Shared as a portfolio sample
with the team's agreement. Code is MIT licensed (see `LICENSE`); course data is
not redistributed and not covered by the licence.*
