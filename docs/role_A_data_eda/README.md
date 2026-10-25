# Role A, Data & EDA

**Owner:** Van · **Status:** assigned

Drop here the document(s) this role produces (any format: `.md`, `.docx`,
`.pdf`) **and any supporting files** (profile figures, small CSVs, notes).

**Covers in the report:** Method §data (dataset description, cleaning),
Experiments §dataset/EDA (daily profiles, weekday vs weekend).

**Suggested file naming:** `A_<topic>_<name>.<ext>` (e.g. `A_eda_writeup_van.docx`).

## Files dropped here (v2, tested on Kaggle)
- `process_sunt.py` : v2 ingestion + streaming EDA + per-stop RegressionInstance handle
- `eda_plots/` : 10 per-stop weekday vs weekend boarding profiles
- `A_README.md`, `output_log.md` : A's v2 notes and run log
- `A_report_draft.md` : starter draft for the report (Method/Data + Experiments/EDA)

## Where the working code lives (for Roles B-F)
- The importable module is at the **repo root**: `from process_sunt import get_stop_stream, get_all_stop_streams, ALL_STOPS` (run from the project root). The copy here in `docs/` is the role record.
- The 10 EDA figures are mirrored into `../../figures/` (the report pulls figures from there).
- NOTE for the team: `process_sunt.py` overlaps with the earlier skeleton `src/data.py` (both load the SUNT data). Pick ONE canonical data layer so we don't maintain two divergent loaders. Recommended: use `process_sunt.py` (Van's, tested) and retire/forward `src/data.py`.
