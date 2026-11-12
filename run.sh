#!/usr/bin/env bash
# One command to run door counting: set up the venv, fetch the weights, make
# sure the counting lines are drawn, then run.
#
#   ./run.sh                     # default video, --status
#   ./run.sh --bbox              # same, plus boxes
#   ./run.sh --video my.mp4      # your own video

set -e
cd "$(dirname "$0")"
VENV=".venv"
PY="$VENV/bin/python"

# 1. virtual environment
if [ ! -x "$PY" ]; then
    echo ">> creating virtual environment at $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -r requirements.txt
fi

# 2. model weights
mkdir -p weights
if [ ! -f weights/yolo26s.pt ]; then
    echo ">> downloading yolo26s.pt via ultralytics"
    "$PY" -c "from ultralytics import YOLO; YOLO('yolo26s.pt')"
    [ -f yolo26s.pt ] && mv yolo26s.pt weights/
fi

# 3. your own video: pass straight through
if [[ "$*" == *"--video"* ]]; then
    exec "$PY" inference.py "$@"
fi

# 4. default video: draw the lines first if the config has none
DEFAULT_VIDEO="./videos/entrance_door_cleaned.mp4"
HAS=$("$PY" -c "import yaml; c=yaml.safe_load(open('configs/counting.yaml')); print(1 if c['counting'].get('lines') else 0)")
if [ "$HAS" != "1" ]; then
    echo ">> no counting lines yet - draw them (click 2 points per line, s to save)"
    "$PY" draw_line.py --video "$DEFAULT_VIDEO"
fi

# 5. run (default + any extra flags like --bbox)
exec "$PY" inference.py --video "$DEFAULT_VIDEO" --status "$@"
