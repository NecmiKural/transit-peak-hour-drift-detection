"""Central configuration for the Concept Drifters A3 project.

Keep all paths, dataset IDs, the chosen stops, and the peak/drift
hyper-parameters here so experiments are reproducible and the rest of
the code stays parameter-free.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
for _p in (DATA_RAW, DATA_PROC, FIGURES):
    _p.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------- reproducibility
# Fixed seed for reproducibility.
SEED = 42

# ------------------------------------------------------------- dataset
# The assignment's 10-stop subset (NOT the full suntdataset firehose).
HF_REPO_5MIN = "labiaufba/SSA_StopBusTimeSeries_5"    # 5-minute aggregation
HF_REPO_30MIN = "labiaufba/SSA_StopBusTimeSeries"      # 30-minute aggregation
HF_FILES = {
    "boarding": "boarding_03-05_2024.csv",   # estimated boardings per stop
    "landing": "landing_03-05_2024.csv",     # estimated alightings per stop
    "loader": "loader_03-05_2024.csv",       # estimated bus occupancy
}
FREQ = "5min"
# Data window (from the filename): March–May 2024. No carnival in this subset.
DATE_START = "2024-03-01"
DATE_END = "2024-05-31"

# ------------------------------------------------------- the 10 stops
# id -> (short label, type). Types drive the weekday/weekend drift story.
STOPS = {
    "44783654": ("UFBA university", "commuter/education"),
    "43768720": ("Lapa Station", "hub/commuter"),
    "230565994": ("Itapua Beach", "leisure"),
    "125960550": ("Arena Fonte Nova", "event"),
    "45833547": ("Barradao Stadium", "event"),
    "44784438": ("Ferry Boat terminal", "intercity"),
    "47568123": ("Shopping mall", "commercial"),
    "44072192": ("Castro Alves Theater", "evening/event"),
    "258781031": ("Salvador Bus Station", "hub/intercity"),
    "44783914": ("Lacerda Elevator", "tourist/commercial"),
}

# Proposed Day-1 starting subset: clearest weekday-vs-weekend contrast.
# (UFBA = weekday commuter, Lapa = hub, Itapua = weekend leisure.)
START_SUBSET = ["44783654", "43768720", "230565994"]

# Salvador timezone, align all external data to this.
TZ = "America/Bahia"  # UTC-3
LAT, LON = -12.9777, -38.5016  # Salvador for Open-Meteo

# ---------------------------------------------- peak-boundary detection
# Online adaptive baseline of the boarding rate (all incremental).
EWMA_ALPHA = 0.05      # smoothing for the running mean/var of the off-peak rate
THRESH_K = 2.5         # peak when rate > running_mean + K * running_std ...
MIN_ABS_LIFT = 3.0     # ... and at least this many extra boardings above baseline
MIN_SUSTAIN = 4        # consecutive intervals (=20 min) above threshold to confirm

# Only search for the morning/evening peak start inside these minute-of-day
# windows, so random night noise isn't mistaken for a peak. The exact start
# inside the window is still found from the data, not fixed.
AM_WINDOW = (4 * 60, 11 * 60)    # 04:00-11:00
PM_WINDOW = (15 * 60, 22 * 60)   # 15:00-22:00

# Reliability gate for the boundary analysis. Several of the 10 stops carry
# almost no demand in this Mar-May 2024 window (Arena Fonte Nova ~0/day,
# Barradao ~2/day, Itapua ~36/day = stadium off-season / beach stop), so a
# "peak boundary" there is meaningless. A (stop, period) result is reported as
# RELIABLE only when the stop has real demand AND the detector fired on enough
# days; everything is still written out, just flagged, for transparency.
MIN_DAILY_DEMAND = 100   # mean weekday boardings/day below this -> negligible demand
MIN_PEAK_DAYS = 15       # fewer detected peak-days than this -> too sparse to trust

# Official windows we compare against (the "naive baseline").
OFFICIAL_AM = ("06:00", "09:00")
OFFICIAL_PM = ("17:00", "20:00")

# ----------------------------------------------------- drift detection
ADWIN_DELTA = 0.002
PAGE_HINKLEY_DELTA = 0.005

# ------------------------------- schedule alignment (Role D, GTFS stop_times)
# Scheduled-service peak is extracted from the GTFS arrival profile with the
# same "mean + K*std sustained inside the AM/PM window" rule as the demand
# detector (src/peaks.py), but with profile-scaled params (arrival counts, not
# boardings, so no absolute-lift floor is used here).
SCHED_THRESH_K = 0.5      # scheduled peak = arrivals > day mean + K*std
SCHED_MIN_SUSTAIN = 3     # consecutive 5-min bins to confirm the scheduled peak
SCHED_SMOOTH_BINS = 3     # rolling-mean smoothing (15 min) so steady-headway
#                           schedules still reveal their busiest ramp-up
