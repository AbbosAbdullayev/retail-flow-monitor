"""Download the evaluation videos and the result (output) videos from Google
Drive. Paste each file's id below, then run:  python download.py

A file id is the part between /d/ and /view in a Drive share link, e.g.
https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view  ->  1AbCdEfGhIjKlMnOp
"""
from pathlib import Path

try:
    import gdown
except ImportError:
    raise SystemExit("gdown is not installed. Run: pip install gdown")

BASE = Path(__file__).resolve().parent.parent / "queue-count"   # download into queue-count/

# input clips used for evaluation  ->  queue-count/videos/
INPUT_VIDEOS = {
    "videos/supermarket_demo.mp4": "REPLACE_WITH_FILE_ID",
    "videos/cctv_demo1.mp4": "REPLACE_WITH_FILE_ID",
}

# annotated outputs (faces blurred)  ->  queue-count/results/
RESULT_VIDEOS = {
    "results/supermarket_demo_out.mp4": "REPLACE_WITH_FILE_ID",
    "results/cctv_demo1_out.mp4": "REPLACE_WITH_FILE_ID",
}


def fetch(mapping: dict, label: str) -> None:
    print(f"== {label} ==")
    for rel, file_id in mapping.items():
        dest = BASE / rel
        if dest.exists():
            print("  have:", rel)
            continue
        if "REPLACE" in file_id:
            print("  skip (no file id yet):", rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        gdown.download(id=file_id, output=str(dest), quiet=False)


if __name__ == "__main__":
    fetch(INPUT_VIDEOS, "evaluation videos")
    fetch(RESULT_VIDEOS, "result videos")
    print("done.")
