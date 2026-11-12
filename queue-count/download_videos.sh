#!/usr/bin/env bash
# Download the evaluation clips and the annotated result videos from Google Drive.
set -e
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

"$PY" -m pip install --quiet gdown
"$PY" "$ROOT/src/download.py"
