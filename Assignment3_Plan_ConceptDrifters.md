# Assignment 3 - Project Plan
### Team: Concept Drifters · COMPX523-26A (Machine Learning for Data Streams)
**Topic #4 - Peak-Hour Boundary Detection: *When does rush hour really start?***

> Data-driven, **online** detection of the true start/end of morning & evening peaks at each bus stop in Salvador, and detection of how those boundaries **drift** across weekdays, weekends, public holidays and rainy days. Output is an **actionable** schedule recommendation a transit operator can act on.

---

## 0. TL;DR (read this first)

- **What we build:** a streaming pipeline that, stop-by-stop and interval-by-interval, (a) learns the demand pattern online, (b) detects the *real* peak window each day with an adaptive threshold, and (c) uses a drift detector (ADWIN / Page-Hinkley) to flag when those peak boundaries **shift** over the year.
- **The "so what":** *"Stop X's real morning peak now starts at 06:20, not the scheduled 05:45 - and on rainy days it starts ~15 min earlier and runs ~30% heavier. Move the first reinforcement trip earlier and add N vehicles."*
- **Hard rule we must respect:** **online/streaming models only** (MOA / CapyMOA). Any batch algorithm = **50% penalty**. Everything must be incremental (test-then-train).
- **Dataset:** SUNT (Salvador), **5-minute** aggregation version (we need fine time resolution to find boundaries). Combine with **external data** (weather, public holidays) - the lecturer explicitly rewards this.
- **Dates:** start **Sat 20 Jun**, submit **Wed 24 Jun**, present **Thu 25 Jun** (10 min + 5 min Q&A, slides on Moodle by 12:00).

---

## 1. The problem (framing)

Operators schedule extra "peak-hour" service using fixed, official windows (e.g. 06:00–09:00, 17:00–20:00). But the **real** demand peak at a given stop may start earlier/later, be sharper, or move over time. If the schedule and the real peak are misaligned, buses arrive when demand has already piled up.

We answer three questions, **all computed online over the data stream**:

1. **Where is the real peak?** For each stop, detect the data-driven start/end of the morning and evening peaks (not the official ones).
2. **Do the boundaries drift?** Track how the detected peak start/end move across weekday vs weekend, public holidays, and rainy days (our data covers March–May 2024).
3. **Why do they drift?** Correlate boundary shifts with **external signals** - rain (Open-Meteo) and public holidays (Good Friday, Tiradentes, Labour Day in our window).

**Deliverable insight (actionable):** a per-stop "true peak window" table + drift alerts + a concrete scheduling recommendation. This is exactly the "actionable, the operator can act on it" bar the lecturer set (his counter-example: *"finding that traffic in Salvador is bad is useless - nobody can act on it"*).

---

## 2. Why this fits the brief (constraints checklist)

| Requirement (from brief) | How we satisfy it |
|---|---|
| Online/streaming model only (MOA/CapyMOA); batch = 50% penalty | Everything incremental: online regressor + online classifier + streaming change detector, evaluated **prequentially (test-then-train)**. No `sklearn` fit on full data. |
| Meaningful problem from the transit dataset | Real peak-window detection + drift - directly operational. |
| Actionable result for Salvador gov/operator | Schedule-shift + vehicle-allocation recommendation per stop. |
| Encouraged: combine with external public data | Open-Meteo weather + Brazilian/Bahia public-holiday calendar. |
| Report: 4–6 page research paper (LaTeX), full structure + CRediT | Sec. 9 outline; CRediT paragraph; Overleaf (Elsevier simple layout). |
| All code submitted + fully reproducible (else −25% technical) | Repo with fixed seeds, `requirements.txt`, `README`, one-command run. |
| If dataset modified, submit modified data + description of changes | We log every transform; ship processed CSVs + a `CHANGES.md`. |
| Presentation 25 Jun, 10 min + 5 Q&A, 2 presenters (1 nominated, 1 by random.org) | Sec. 10; everyone rehearses so any member can present/answer. |

---

## 3. Data plan

**Use the 5-minute version.** Peak boundaries are a fine-grained timing question; 30-min buckets are too coarse to locate a 06:20 vs 05:45 boundary.

**The dataset is the 10-stop subset on Hugging Face** (linked from the brief), not the full network:
- 5-min: `labiaufba/SSA_StopBusTimeSeries_5` · 30-min: `labiaufba/SSA_StopBusTimeSeries`
- Three small CSVs (~1 MB each): `boarding` (estimated boardings/stop), `landing` (estimated alightings), `loader` (estimated bus occupancy), plus a `gtfs/` folder.
- Format: wide **time × stop** (rows = 5-min timestamps, columns = the 10 stops).
- **Window: March–May 2024 only** (so there is **no carnival** in this data, our drift story is weekday/weekend/holiday/rain, not seasonal).

**The 10 stops** (great contrast for peak boundaries): UFBA university (44783654, weekday commuter), Lapa Station (43768720, hub), Itapuã beach (230565994, weekend/leisure), Arena Fonte Nova (125960550) & Barradão stadium (45833547, events), Ferry terminal (44784438), shopping mall (47568123), Castro Alves theater (44072192, evenings), Salvador Bus Station (258781031), Lacerda Elevator (44783914, tourist).

**Loading:** download the CSVs from HF (`huggingface_hub.hf_hub_download`) and read with pandas, the data is tiny, so it fits easily in memory and we just stream the rows in time order. (`pip install suntdataset` is a separate package that loads the *full* network for all ~2700 stops over a year; optional, not needed for this subset.)

**Key fields we rely on:** boardings per (timestamp, stop); weekday vs weekend is derived from the timestamp; stop metadata via GTFS. Salvador timezone is **UTC−3** - align all external data to this.

**External data to merge (timestamp-joined):**
- **Weather:** Open-Meteo historical API (free, no key) - hourly rain/precip, temperature for Salvador (Mar–May 2024).
- **Calendar:** Brazilian/Bahia public holidays in the window, Good Friday (29 Mar), Tiradentes (21 Apr), Labour Day (1 May) 2024, to test whether boundaries shift on holidays.

---

## 4. Methodology (the streaming pipeline)

Process each stop's boardings as a **time-ordered stream** of 5-min intervals across the whole year. Three online components run together:

**(A) Online demand model - regression.**
Predict next-interval boarding volume from streaming features (time-of-day, day-of-week, `day_type`, recent lags/rolling rate, weather, holiday flag). Evaluate prequentially.
- CapyMOA: `from capymoa.regressor import AdaptiveRandomForestRegressor` (FIMTDD-based, handles drift internally), plus `FIMTDD` / `KNNRegressor` / `PassiveAggressiveRegressor` as baselines.

**(B) Adaptive peak detection - the boundary finder (online).**
Maintain an **incremental** baseline of the boarding rate (EWMA mean + variance, or the model's expected rate). An interval is "peak" when the smoothed rate crosses an adaptive threshold (e.g. `mean + k·std`, updated online). The **first sustained up-crossing each morning = morning-peak start**; symmetric logic for peak end and the evening peak. Nothing here needs the full day in memory - it's all incremental.

**(C) Drift detection on the boundaries - the headline result.**
Feed the per-day boundary timestamps (and/or the regression residuals / boarding-rate stream) into a streaming change detector to flag when the boundary regime shifts:
- CapyMOA: `from capymoa.drift.detectors import ADWIN, PageHinkley` - usage `det = ADWIN(delta=0.001)`, then per value `det.add_element(x); if det.detected_change(): ...`. ADWIN = robust default (parameter-free except δ); Page-Hinkley/CUSUM = good for abrupt shifts; DDM/EDDM if we frame a classifier's error stream.

**Optional complementary task - online classification (peak vs off-peak).**
Frame each interval as peak/off-peak and run `HoeffdingTree` / `AdaptiveRandomForestClassifier`; report **Kappa / Kappa-M** (class imbalance) on windowed prequential. Gives a second, model-based view and more parallel work for the team.

**Evaluation (course-mandated):**
- **Prequential / interleaved test-then-train** via `from capymoa.evaluation import prequential_evaluation`.
- **Windowed** metrics (sliding window / fading factor) - `plot_windowed_results` - so drift periods are visible.
- Regression: **RMSE, MAE** (+ RSE/RRSE). Classification: **Kappa / Kappa-M**.
- **Baselines** to beat: official fixed peak windows; a naïve "yesterday/last-week same interval" predictor.

---

## 5. The actionable output (the centrepiece)

A small artifact + 2–3 punchy findings, e.g.:

- **Per-stop true-peak table:** real morning/evening peak windows vs the official/scheduled ones.
- **Drift alerts:** "Stop X morning-peak start is ~06:20 on weekdays but absent on weekends"; "on a rainy morning the peak started ~15 min earlier and ran heavier".
- **Weather effect:** "on rainy mornings the peak starts ~15 min earlier and is ~30% heavier."
- **Recommendation:** concrete schedule shift + extra-vehicle allocation per stop/corridor, phrased as something the operator can put into the GTFS timetable.

---

## 6. Team split (6 people)

We don't have names wired in yet - assign A–F at kickoff. Roles are sized so work runs in parallel and every member owns a report section.

| Role | Owner | Responsibilities |
|---|---|---|
| **A. Data & EDA lead** | Van | Download the 10-stop HF subset (`SSA_StopBusTimeSeries_5`); load 5-min boarding (time×stop); clean & handle missing dates; EDA + first peak visualizations; start with UFBA, Lapa, Itapuã. |
| **B. External data & features** | Aryan | Open-Meteo weather + Brazilian/Bahia public-holiday calendar for Salvador (UTC−3); timestamp-join; build streaming features (time-of-day, day-of-week, lags, rolling rate, rain flag). |
| **C. Streaming modeling lead** | Hans | CapyMOA online regressor (ARF-Reg/FIMTDD) + optional peak/off-peak classifier; prequential setup; baselines. |
| **D. Change-point / drift lead** | Necmi | Adaptive-threshold boundary extraction; ADWIN/Page-Hinkley on boundaries; weekday/weekend/holiday drift tracking; correlate shifts with weather/holidays. |
| **E. Evaluation & viz / reproducibility** | Saurabh | Prequential & windowed plots (RMSE/MAE/Kappa), boundary-over-time charts with drift markers, baseline comparison; own the repo, seeds, `requirements.txt`, `README`, one-command reproduce. |
| **F. Report & presentation lead / PM** | Eugene | Overleaf paper assembly, CRediT, slide deck, timeline & submission checklist; coordinates everyone; default presenter. |

Everyone writes the report paragraphs for their part and contributes their slides. **Two presenters** (one nominated + one drawn by random.org), so **all six must understand the whole pipeline** for Q&A.

---

## 7. Day-by-day timeline (20–25 Jun)

| Day | Goal | Key deliverables |
|---|---|---|
| **Sat 20 Jun - Kickoff** | Environment + data flowing + scope locked | Everyone installs CapyMOA (needs **Java 17**) + downloads the 10-stop HF subset; repo skeleton; agree scope (which stops, peak definition); assign A–F; A starts EDA. |
| **Sun 21 Jun - Foundations** | Data + features + skeleton pipeline | EDA done with peak plots; external data fetched & joined (B); end-to-end streaming skeleton runs (load → prequential → RMSE) on 1 stop (C/E). |
| **Mon 22 Jun - Core methods** | Models + boundary + drift working | Regressor (+ classifier) prequential results (C); adaptive boundary extraction + ADWIN/Page-Hinkley producing first boundary-drift results (D). |
| **Tue 23 Jun - Experiments & analysis** | Full results across stops | Weekday/weekend/seasonal drift; weather/holiday correlation; baseline comparison; final figures (D/E); draft all report sections (all); start slides (F). |
| **Wed 24 Jun - Freeze & SUBMIT** | Report + code submitted | 4–6 page report finalized (incl. CRediT + reproducibility); clean code repo + modified-data + `CHANGES.md`; **submit**; slides near-final. |
| **Thu 25 Jun - Present** | Deliver | Rehearse to 10:00 (warnings at 5/8/10); upload slides to Moodle **before 12:00**; present (2 presenters); all ready for 5-min Q&A. |

> Buffer: keep Tue night / Wed morning as slack. The CapyMOA + **Java 17** setup is the usual snag, sort it by **end of Sat**; the data download itself is trivial (~1 MB).

---

## 8. Report outline (4–6 pages, Elsevier/LaTeX)

1. **Title + author list** (all 6).
2. **Abstract** - problem, online method, headline actionable result.
3. **Introduction** - official vs real peaks; why it matters operationally; contributions.
4. **Related work** - streaming ML & drift detection (ADWIN, Page-Hinkley, ARF); transit demand / peak & change-point analysis.
5. **Proposal / method** - data + external fusion; streaming features; online models; adaptive boundary detection; drift tracking.
6. **Experiments** - prequential setup; model accuracy (RMSE/MAE/Kappa, windowed); detected peak windows; boundary drift (weekday/weekend/holiday); weather/holiday effects; baselines.
7. **Discussion** - concrete recommendations for Salvador's operator; limitations (no ground-truth labels → unsupervised; don't overclaim).
8. **Conclusion + future work.**
9. **References** (may exceed the page limit; ~1 page).
10. **CRediT paragraph** - one line per member (Conceptualization, Data curation, Methodology, Software, Validation, Visualization, Writing, Project administration…).

**Note on AI use:** brief allows LLMs for *light editing only* - not fully AI-generated text. (See open question on whether chat logs must be attached.)

---

## 9. Presentation plan (10 min, ~10–12 slides)

1. Title + team.
2. Problem & motivation - official vs real rush hour.
3. Data - SUNT 5-min + external (weather/holidays).
4. Why streaming (the constraint + the real-time framing).
5. Method overview - one clean pipeline diagram.
6. Online models + prequential evaluation.
7. Boundary detection + drift method (ADWIN / Page-Hinkley).
8. Result 1 - detected true peak windows per stop.
9. Result 2 - boundary drift across weekday/weekend/holiday + weather effect.
10. **Actionable recommendation** - the operator action (the slide that wins marks).
11. Limitations + conclusion.
12. *(Backup slides for Q&A: metrics, parameter choices, extra stops.)*

Optional **1–2 min video** (animate the peak boundary drifting over the year) - must be included in the submission if used. Rehearse to land at ~9:30.

---

## 10. Risks & mitigations

- **"Is it really online?"** (biggest grading risk) - keep *everything* incremental, document the test-then-train loop, never call `.fit()` on the full dataset. State it explicitly in the report.
- **CapyMOA + Java 17 setup** - the usual snag; verify Day 1. The HF data download is trivial (~1 MB).
- **No ground-truth peak labels** - frame boundary detection as *unsupervised change detection*; do a sensitivity analysis on the threshold `k`; don't overclaim accuracy.
- **External-data join / timezone** - Salvador is UTC−3; align carefully or correlations break.
- **Scope creep over 10 stops** - start with 3 contrast stops (UFBA, Lapa, Itapuã), scale to all 10 once the pipeline is solid.
- **Reproducibility (−25%)** - fixed seeds, `requirements.txt`, `README`, single reproduce script; one person (E) owns this.

---

## 12. Submission checklist (Wed 24 Jun)

- [ ] 4–6 page report PDF (LaTeX), full structure + **CRediT** paragraph.
- [ ] All code - **only the necessary files**, runnable & reproducible (seed, `requirements.txt`, `README`, one-command run).
- [ ] Modified datasets + `CHANGES.md` describing every transform.
- [ ] (If used) 1–2 min video included in the submission.
- [ ] Slides uploaded to Moodle **before 12:00 on Thu 25 Jun**.
- [ ] Group registered on the MS Form (should already be done).
- [ ] (If required) LLM chat logs included.
