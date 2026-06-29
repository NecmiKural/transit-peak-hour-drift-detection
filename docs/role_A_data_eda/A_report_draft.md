# Role A - report draft (suggestion for Van)

Starting draft for the two paper subsections Role A owns. Numbers come from the
v2 pipeline run; please confirm the EDA findings against your plots and edit
freely. Paste into `docs/report_sections/04_method.md` (Data) and
`05_experiments.md` (Dataset & EDA) once happy.

## Method - Data

We use the SUNT 10-stop subset at 5-minute aggregation
(`labiaufba/SSA_StopBusTimeSeries_5`) for Salvador, Brazil, covering 1 March to
31 May 2024 (local time, UTC-3). The data is wide-format: rows are 5-minute
timestamps and columns are the 10 selected stops, with three parallel series per
stop (boardings, alightings, and vehicle occupancy). Boardings are our primary
signal; alightings and occupancy are retained as features.

Ingestion is fully streaming: the CSVs are pulled programmatically from Hugging
Face and read in 1,000-row micro-chunks, so no full table is held in memory
(O(1) footprint, consistent with the online-only constraint). Cleaning is done
in-stream: timestamps are strictly filtered to the study window and validated
against an explicit format guard, and a per-chunk row-count guard prevents the
three CSV files from silently misaligning. Missing 5-minute slots are imputed
online using a per-(time-of-day, stop) exponentially weighted moving average
(alpha = 0.05) built only from previously seen values, and each imputed record is
flagged (`data_valid = 0`) so downstream models can drop or down-weight it. Over
the window this yields 218,400 real records and 43,200 imputed records (261,600
total across the 10 stops), an empirical availability of 83.5%.

The data layer exposes, for each stop, a stream of CapyMOA `RegressionInstance`
objects whose target is the next boarding count and whose features are calendar
and context variables (hour, minute, day-of-week, alightings, occupancy,
validity flag). No peak labels or instance weights are introduced at this stage:
peak-boundary detection and any weighting are downstream decisions.

## Experiments - Dataset and EDA

We characterise each stop by its mean 5-minute boarding count as a function of
hour of day, separated into weekday and weekend profiles (Figures
`eda_boardings_stop_*.png`). The profiles differ markedly by stop type, which
motivates per-stop, data-driven boundary detection rather than a single fixed
city-wide rush-hour window. Commuter hubs such as Lapa Station show a pronounced
weekday morning ramp and a strong evening peak that largely flatten at weekends,
whereas leisure-oriented stops such as Itapua beach show weekend-skewed demand.
[Van: confirm the exact shapes and call out 2-3 representative stops from the
figures.]

These observations set up the core question: where do the real peak boundaries
sit per stop, and do they move across weekday, weekend, and holidays? That is
addressed by the boundary-detection and drift analysis (Role D).
