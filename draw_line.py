"""Draw the two counting lines over the playing video and save them to
configs/counting.yaml. Click two points per line, s to save."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import cv2

CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "counting.yaml"

pending: list[tuple[int, int]] = []           # first click of the line being drawn
lines: list[list[tuple[int, int]]] = []       # completed lines


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        pending.append((x, y))
        if len(pending) == 2:
            lines.append([pending[0], pending[1]])
            pending.clear()


def save_lines() -> None:
    parts = ", ".join(f"[[{a[0]}, {a[1]}], [{b[0]}, {b[1]}]]" for a, b in lines)
    value = f"[{parts}]"
    text = CONFIG_PATH.read_text()
    text = re.sub(r"(?m)^(\s*lines:).*$", rf"\g<1> {value}   # counting lines; set with draw_line.py", text)
    CONFIG_PATH.write_text(text)
    print(f"Saved {len(lines)} line(s) to {CONFIG_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw counting lines over the playing video.")
    parser.add_argument("--video", type=str, required=True, help="Full path to the video file.")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {args.video}")
    delay = int(1000 / (cap.get(cv2.CAP_PROP_FPS) or 25))

    cv2.namedWindow("draw-line")
    cv2.setMouseCallback("draw-line", on_mouse)
    print("Click 2 points per line | s: save | z: undo last | r: reset | q: quit (no save)")

    while True:
        ok, frame = cap.read()
        if not ok:                                  # loop the video so playback continues
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        for a, b in lines:
            cv2.line(frame, a, b, (0, 0, 255), 2)
        for p in pending:
            cv2.circle(frame, p, 5, (0, 0, 255), -1)

        cv2.imshow("draw-line", frame)
        key = cv2.waitKey(delay) & 0xFF
        if key == ord("s"):
            save_lines()
            break
        if key == ord("z") and lines:
            lines.pop()
        if key == ord("r"):
            lines.clear()
            pending.clear()
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
