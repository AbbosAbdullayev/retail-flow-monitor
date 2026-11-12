#!/usr/bin/env bash
# Download the door-counting sample and result videos from Google Drive.
set -e
cd "$(dirname "$0")"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

"$PY" -m pip install --quiet gdown
"$PY" download.py
