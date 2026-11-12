"""Door counting: detect and track people, count IN/OUT across two lines, and
write a per-window CSV. Draws the band and blurs the boxes of incoming people."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import yaml

from src.counter import DualLineCounter
from src.detector import Detector
from src.recorder import Recorder
from src.tracker import Tracker

CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "counting.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run detection + tracking on a video.")
    parser.add_argument("--video", type=str, required=True, help="Full path to the video file.")
    parser.add_argument("--save", help="Optional output path to write the annotated video.")
    parser.add_argument("--bbox", action="store_true", help="Also draw corner-bracket boxes.")
    parser.add_argument("--status", action="store_true", help="Show each ID's current zone.")
    return parser.parse_args()


ORANGE = (0, 165, 255)


def draw_corner_box(frame, x1, y1, x2, y2, pad=4):
    x1, y1, x2, y2 = int(x1) - pad, int(y1) - pad, int(x2) + pad, int(y2) + pad
    length = max(6, int(min(x2 - x1, y2 - y1) * 0.2))  # corner arm length
    for cx, sx in ((x1, 1), (x2, -1)):
        for cy, sy in ((y1, 1), (y2, -1)):
            cv2.line(frame, (cx, cy), (cx + sx * length, cy), ORANGE, 1)
            cv2.line(frame, (cx, cy), (cx, cy + sy * length), ORANGE, 1)


def blur_bbox(frame, x1, y1, x2, y2):
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = int(x2), int(y2)
    roi = frame[y1:y2, x1:x2]
    if roi.size:
        frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (0, 0), 10)


def draw(frame, tracks, counter, show_bbox=False, show_status=False):
    # Band = closed trapezoid: outer line, right edge, inner line, left edge.
    up, down = counter.lines["up"], counter.lines["down"]
    corners = [tuple(up[0]), tuple(up[1]), tuple(down[1]), tuple(down[0])]
    for i in range(4):
        cv2.line(frame, corners[i], corners[(i + 1) % 4], (0, 0, 255), 2)
    cv2.putText(
        frame, f"IN {counter.in_count}   OUT {counter.out_count}", (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2,
    )

    # Privacy: blur the box of incoming people (crossed the upper line first).
    for x1, y1, x2, y2, track_id, *_ in tracks:
        if counter.is_entering(track_id):
            blur_bbox(frame, x1, y1, x2, y2)

    if show_bbox:
        # Faint translucent rectangles connecting the corners, blended in one pass.
        overlay = frame.copy()
        for x1, y1, x2, y2, *_ in tracks:
            cv2.rectangle(overlay, (int(x1), int(y1)), (int(x2), int(y2)), ORANGE, 1)
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

    for x1, y1, x2, y2, track_id, *_ in tracks:
        if show_bbox:
            draw_corner_box(frame, x1, y1, x2, y2)
        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
        cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
        label = str(int(track_id))
        if show_status:
            label += f" {counter.status(track_id)}"
        cv2.putText(
            frame, label, (cx + 8, cy - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
        )
    return frame


def main() -> None:
    args = parse_args()

    detector = Detector()
    tracker = Tracker()
    config = yaml.safe_load(CONFIG_PATH.read_text())
    cfg = config["counting"]
    counter = DualLineCounter(
        cfg["lines"],
        confirm_frames=cfg.get("confirm_frames", 3),
        cooldown=cfg.get("cooldown", 25),
        min_age=cfg.get("min_age", 5),
        min_travel=cfg.get("min_travel", 30),
    )

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {args.video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    recorder = Recorder(Path(args.video).stem, fps, config.get("recording", {}))

    writer = None
    if args.save:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        detections = detector.detect(frame)
        tracks = tracker.update(detections, frame)
        counter.update(tracks)
        recorder.update(tracks, counter)
        frame = draw(frame, tracks, counter, args.bbox, args.status)

        if writer:
            writer.write(frame)
        cv2.imshow("people-count", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    recorder.close(counter)
    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
