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
  Processed 50,000 records (8,160 imputed gaps so far)...
  Processed 100,000 records (16,320 imputed gaps so far)...
  Processed 150,000 records (24,960 imputed gaps so far)...
  Processed 200,000 records (33,120 imputed gaps so far)...
  Processed 250,000 records (41,280 imputed gaps so far)...

Stream summary:
  Total records (real + imputed) : 261,600
  Real sensor records            : 218,400
  Imputed gap records            : 43,200
  Empirical availability         : 83.49%

--- Phase 4: EDA Plot Generation ---
  Plotting: Lapa Station Hub (stop 43768720) ...
    Saved: eda_plots\eda_boardings_stop_43768720.png
  Plotting: UFBA University Gate (stop 44783654) ...
    Saved: eda_plots\eda_boardings_stop_44783654.png
  Plotting: Itapua Beach Leisure (stop 230565994) ...
    Saved: eda_plots\eda_boardings_stop_230565994.png
  Plotting: Arena Fonte Nova Stadium (stop 125960550) ...
    Saved: eda_plots\eda_boardings_stop_125960550.png
  Plotting: Barradao Stadium (stop 45833547) ...
    Saved: eda_plots\eda_boardings_stop_45833547.png
  Plotting: Ferry Terminal (stop 44784438) ...
    Saved: eda_plots\eda_boardings_stop_44784438.png
  Plotting: Shopping Mall Corridor (stop 47568123) ...
    Saved: eda_plots\eda_boardings_stop_47568123.png
  Plotting: Castro Alves Theater (stop 44072192) ...
    Saved: eda_plots\eda_boardings_stop_44072192.png
  Plotting: Salvador Bus Station Terminal (stop 258781031) ...
    Saved: eda_plots\eda_boardings_stop_258781031.png
  Plotting: Lacerda Elevator Tourist (stop 44783914) ...
    Saved: eda_plots\eda_boardings_stop_44783914.png

Phase 4 complete. All EDA plots saved to 'eda_plots/'.

Role A pipeline complete.

CapyMOA downstream handle ready.
  - get_stop_stream(stop_id)  -> single-stop RegressionInstance generator
  - get_all_stop_streams()    -> dict of all 10 stop generators
  - ALL_STOPS                 -> dict of stop metadata