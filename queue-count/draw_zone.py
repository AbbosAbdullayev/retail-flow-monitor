"""Draw the polygon zones for a video and save them under its name in
config.yaml. Loops through zone_names; click points, s to save."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import cv2
import numpy as np
import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

points: list[tuple[int, int]] = []     # polygon being drawn for the current name


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))


def fmt_zone(areas: list) -> str:
    if not areas:
        return "[]"
    return "[" + ", ".join("[" + ", ".join(f"[{x}, {y}]" for x, y in poly) + "]" for poly in areas) + "]"


def save_all(zones_by_video: dict) -> None:
    """Rewrite the whole `zones:` block (all videos) so other sections keep their comments."""
    lines = ["zones:"]
    for vid, zmap in zones_by_video.items():
        lines.append(f"  {vid}:")
        for n, areas in zmap.items():
            lines.append(f"    {n}: {fmt_zone(areas)}")
    block = "\n".join(lines) + "\n\n"
    text = CONFIG_PATH.read_text()
    text = re.sub(r"(?ms)^zones:.*?(?=^\S|\Z)", block, text, count=1)
    CONFIG_PATH.write_text(text)
    print(f"Saved zones for {len(zones_by_video)} video(s); keys: {', '.join(zones_by_video)}")


def draw_poly(frame, poly, closed, color, fill) -> None:
    if len(poly) >= 3 and fill:
        overlay = frame.copy()
        cv2.fillPoly(overlay, [np.array(poly, np.int32)], color)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
    if len(poly) >= 2:
        cv2.polylines(frame, [np.array(poly, np.int32)], closed, color, 2)
    for p in poly:
        cv2.circle(frame, tuple(p), 4, (0, 255, 255), -1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw the zones for a video (saved under its name).")
    parser.add_argument("--video", type=str, required=True, help="Full path to the video file.")
    args = parser.parse_args()
    source = Path(args.video).stem

    cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    names = (cfg.get("zone_names") or {}).get(source) or []
    if not names:
        raise SystemExit(f"Add 'zone_names: {{{source}: [service_1, staff_1, ...]}}' to config.yaml first.")
    zones_by_video = dict(cfg.get("zones") or {})
    collected = {k: [[list(p) for p in poly] for poly in v]
                 for k, v in (zones_by_video.get(source) or {}).items()}

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {args.video}")
    delay = int(1000 / (cap.get(cv2.CAP_PROP_FPS) or 25))

    cv2.namedWindow("draw-zone")
    cv2.setMouseCallback("draw-zone", on_mouse)
    editing = not collected                      # already have zones -> start in view mode
    idx = 0
    print(f"Video '{source}': "
          + ("no saved zones, drawing." if editing else "zones exist -> press 'c' to change, 'q' to quit."))

    while True:
        ok, frame = cap.read()
        if not ok:                               # loop the video so playback continues
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        if not editing:                          # VIEW mode: show saved zones, wait for c / q
            for areas in collected.values():
                for poly in areas:
                    draw_poly(frame, poly, True, (0, 200, 0), True)
            cv2.putText(frame, f"'{source}' has {len(collected)} zones  |  c: change   q: quit",
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("draw-zone", frame)
            key = cv2.waitKey(delay) & 0xFF
            if key == ord("c"):
                editing, idx = True, 0
                collected.clear()                # redraw from scratch
            elif key == ord("q"):
                break
            continue

        name = names[idx]                        # EDIT mode
        for other, areas in collected.items():   # already-drawn zones (grey)
            if other != name:
                for poly in areas:
                    draw_poly(frame, poly, True, (150, 150, 150), False)
        is_queue = name.startswith("service") or name.startswith("queue")
        draw_poly(frame, points, False, (0, 140, 255) if is_queue else (0, 200, 0), True)
        cv2.putText(frame, f"[{idx + 1}/{len(names)}] draw: {name}   points: {len(points)}",
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, "n next  b back  s save  z undo  r reset  q quit",
                    (20, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.imshow("draw-zone", frame)

        key = cv2.waitKey(delay) & 0xFF
        if key in (ord("n"), ord("b"), ord("s")):
            if len(points) >= 3:
                collected[name] = [[list(p) for p in points]]
            points.clear()
            if key == ord("s"):
                zones_by_video[source] = collected
                save_all(zones_by_video)
                break
            idx = min(idx + 1, len(names) - 1) if key == ord("n") else max(idx - 1, 0)
        elif key == ord("z") and points:
            points.pop()
        elif key == ord("r"):
            points.clear()
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
