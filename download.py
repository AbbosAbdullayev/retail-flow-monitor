"""Download the sample videos from the shared Google Drive folder into videos/.
Run:  python download.py   (or ./download_videos.sh)
"""
from pathlib import Path

try:
    import gdown
except ImportError:
    raise SystemExit("gdown is not installed. Run: pip install gdown")

HERE = Path(__file__).resolve().parent
FOLDER_URL = "https://drive.google.com/drive/folders/12ac4PAFBlsZxEGsz4ktb5EPAbmBU42kD"


if __name__ == "__main__":
    dest = HERE / "videos"
    dest.mkdir(exist_ok=True)
    gdown.download_folder(FOLDER_URL, output=str(dest), quiet=False, use_cookies=False)
    print(f"done -> {dest}")
