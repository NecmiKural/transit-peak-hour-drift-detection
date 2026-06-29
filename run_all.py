"""One-command reproduction of the whole Concept Drifters pipeline.

    python run_all.py            # run every stage in order
    python run_all.py --skip-download   # data already in data/raw/
    python run_all.py --only C          # run a single stage (A/B/C/D/E)

Stages (each reads the previous stage's git-tracked outputs, so you can also
run them individually):

  A  scripts/01_download_data.py        fetch HF CSVs + GTFS            [needs internet/HF]
  B  scripts/02_build_features.py       build features_stream.csv      [needs weather API]
  C  python -m src.pipeline             prequential ARF vs baselines   [needs Java 17 + CapyMOA]
  D1 scripts/03_drift_analysis.py       peak boundaries + drift        [offline ok]
  D2 scripts/04_schedule_alignment.py   schedule vs demand gap         [needs gtfs/stop_times.txt]
  E  docs/.../Evaluation.ipynb          polished tables + figures      [nbconvert]

IMPORTANT, canonical drift result: stage D1 runs a DEV change-detector when
CapyMOA/Java 17 is not installed (it writes role_d_concept_drift_offline.csv).
The result reported in the paper is the real CapyMOA ADWIN run produced by
`scripts/kaggle_drift_run.py` on Kaggle (Java 17), committed as
`outputs/role_d_concept_drift.csv`. run_all.py never overwrites that file.

All intermediate outputs are git-tracked, so a grader can inspect every result
without re-running anything; this script just makes a full re-run repeatable.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

STAGES = [
    ("A", "Download data (HF CSVs + GTFS)", [PY, "scripts/01_download_data.py"]),
    ("B", "Build feature table (weather + holidays + lags)", [PY, "scripts/02_build_features.py"]),
    ("C", "Role C: prequential ARF vs online baselines", [PY, "-m", "src.pipeline"]),
    ("D1", "Role D: peak boundaries + drift", [PY, "scripts/03_drift_analysis.py"]),
    ("D2", "Role D: schedule-vs-demand alignment", [PY, "scripts/04_schedule_alignment.py"]),
    ("E", "Role E: polished tables + figures",
     [PY, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
      "docs/role_E_evaluation_viz/Evaluation.ipynb"]),
]


def run(parser_args):
    only = parser_args.only.upper() if parser_args.only else None
    results = []
    for key, desc, cmd in STAGES:
        if only and key != only:
            continue
        if parser_args.skip_download and key == "A":
            print(f"\n=== Stage {key}: {desc}, SKIPPED (--skip-download) ===")
            continue
        print(f"\n{'='*70}\n=== Stage {key}: {desc}\n=== $ {' '.join(cmd)}\n{'='*70}")
        rc = subprocess.run(cmd, cwd=ROOT).returncode
        results.append((key, rc))
        if rc != 0:
            print(f"!!! Stage {key} exited with code {rc}.")
            if key in {"C"}:
                print("    (Stage C needs Java 17 + CapyMOA, see README setup.)")
            if not parser_args.keep_going:
                print("    Stopping. Re-run with --keep-going to continue past failures.")
                break
    print(f"\n{'='*70}\nSUMMARY")
    for key, rc in results:
        print(f"  Stage {key}: {'OK' if rc == 0 else f'FAILED (rc={rc})'}")
    print("="*70)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Reproduce the full A3 pipeline")
    ap.add_argument("--skip-download", action="store_true", help="data/raw already populated")
    ap.add_argument("--only", help="run a single stage: A, B, C, D1, D2, E")
    ap.add_argument("--keep-going", action="store_true", help="continue past a failing stage")
    run(ap.parse_args())
