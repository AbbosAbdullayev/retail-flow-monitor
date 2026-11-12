#!/usr/bin/env bash
# One command to run the queue/counter zone monitor.
# Sets up a venv from ../requirements.txt, ensures the model weights, checks the
# zones exist (draws them if not), then runs. Weights/venv are shared with the repo.
#
#   ./run.sh                         # default: supermarket_demo, --status
#   ./run.sh --bbox                  # same, plus boxes
#   ./run.sh --video a.mp4 b.mp4     # your own source(s), multi-stream (as run.py)

set -e
cd "$(dirname "$0")"                     # queue-count/
ROOT="$(cd .. && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"

# 1. virtual environment
if [ ! -x "$PY" ]; then
    echo ">> creating virtual environment at $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -r "$ROOT/requirements.txt"
fi

# 2. model weights (into queue-count/weights, where the code looks)
mkdir -p weights
if [ ! -f weights/yolo26s.pt ]; then
    if [ -f "$ROOT/weights/yolo26s.pt" ]; then
        echo ">> copying yolo26s.pt from repo weights"
        cp "$ROOT/weights/yolo26s.pt" weights/
    else
        echo ">> downloading yolo26s.pt via ultralytics"
        "$PY" -c "from ultralytics import YOLO; YOLO('yolo26s.pt')"
        [ -f yolo26s.pt ] && mv yolo26s.pt weights/
    fi
fi
if [ ! -f weights/osnet_x0_25_msmt17.pt ] && [ -f "$ROOT/weights/osnet_x0_25_msmt17.pt" ]; then
    cp "$ROOT/weights/osnet_x0_25_msmt17.pt" weights/
fi

# 3. custom source(s): pass straight through (run.py checks each video's zones)
if [[ "$*" == *"--video"* ]]; then
    exec "$PY" run.py "$@"
fi

# 4. default source: draw its zones first if the config has none
DEFAULT_VIDEO="./videos/supermarket_demo.mp4"
SRC="supermarket_demo"
HAS=$("$PY" -c "import yaml; c=yaml.safe_load(open('config.yaml')); print(1 if (c.get('zones') or {}).get('$SRC') else 0)")
if [ "$HAS" != "1" ]; then
    echo ">> no zones for $SRC yet - draw them (click points, s to save, q to quit)"
    "$PY" draw_zone.py --video "$DEFAULT_VIDEO"
fi

# 5. run (default + any extra flags like --bbox)
exec "$PY" run.py --video "$DEFAULT_VIDEO" --status "$@"
