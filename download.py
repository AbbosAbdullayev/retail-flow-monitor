"""Download the door-counting sample videos and the result videos from Google
Drive. Paste each file id below, then run:  python download.py

A file id is the part between /d/ and /view in a Drive share link, e.g.
https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view  ->  1AbCdEfGhIjKlMnOp
"""
from pathlib import Path

try:
    import gdown
except ImportError:
    raise SystemExit("gdown is not installed. Run: pip install gdown")

HERE = Path(__file__).resolve().parent

# input clips  ->  videos/
INPUT_VIDEOS = {
    "videos/entrance_demo.mp4": "REPLACE_WITH_FILE_ID",
}

# annotated outputs  ->  results/
RESULT_VIDEOS = {
    "results/entrance_demo_out.mp4": "REPLACE_WITH_FILE_ID",
}


def fetch(mapping: dict, label: str) -> None:
    print(f"== {label} ==")
    for rel, file_id in mapping.items():
        dest = HERE / rel
        if dest.exists():
            print("  have:", rel)
            continue
        if "REPLACE" in file_id:
            print("  skip (no file id yet):", rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        gdown.download(id=file_id, output=str(dest), quiet=False)


if __name__ == "__main__":
    fetch(INPUT_VIDEOS, "sample videos")
    fetch(RESULT_VIDEOS, "result videos")
    print("done.")
