"""Download the assignment's 10-stop 5-minute subset from Hugging Face.

Run once:  python scripts/01_download_data.py
Files land in data/raw/. The dataset is small (~1 MB per CSV).

If your network blocks Hugging Face, run this on Kaggle (the kaggle MCP /
notebooks can reach HF) or download the files manually from:
  https://huggingface.co/datasets/labiaufba/SSA_StopBusTimeSeries_5/tree/main
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

from huggingface_hub import hf_hub_download  # noqa: E402


def main():
    files = list(C.HF_FILES.values()) + [
        "gtfs/stops.txt", "gtfs/calendar.txt",
        "gtfs/trips.txt",       # trip -> service_id (Role D schedule alignment)
        "gtfs/stop_times.txt",  # ~88 MB: scheduled arrivals per stop
    ]
    for fname in files:
        try:
            path = hf_hub_download(
                repo_id=C.HF_REPO_5MIN,
                filename=fname,
                repo_type="dataset",
                local_dir=str(C.DATA_RAW),
            )
            print(f"  ok  {fname}  ->  {path}")
        except Exception as e:  # keep going; gtfs extras are optional
            print(f"  WARN could not fetch {fname}: {e}")
    print("Done. Raw data in", C.DATA_RAW)


if __name__ == "__main__":
    main()
