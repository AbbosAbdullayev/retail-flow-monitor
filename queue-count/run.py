"""Runs the zone monitor on one or more videos. One source plays as fast as
it can; two or more run concurrently (a process each) at real-time, and a
dropped source reconnects on its own. Writes the CSV and alert events."""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time
from pathlib import Path

import cv2
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))          # reuse the main pipeline's detector/tracker
sys.path.insert(0, str(HERE))

from src.detector import Detector      # noqa: E402
from src.tracker import Tracker        # noqa: E402
from monitor import ZoneMonitor        # noqa: E402
from recorder import QueueRecorder     # noqa: E402

CONFIG_PATH = HERE / "config.yaml"

ORANGE = (0, 165, 255)       # default (not in any zone)
QUEUE_COLOR = (255, 255, 0)  # cyan: person in a queue zone
STAFF_COLOR = (255, 0, 255)  # magenta: person in a staff zone
FONT = cv2.FONT_HERSHEY_SIMPLEX


def track_color(monitor, tid):
    z = monitor.zone_of(tid)
    if z in monitor.staff:
        return STAFF_COLOR
    if z in monitor.queues:
        return QUEUE_COLOR
    return ORANGE


def draw_corner_box(frame, x1, y1, x2, y2, color=ORANGE, pad=4):
    """Corner brackets (same style as the people-counting view)."""
    x1, y1, x2, y2 = int(x1) - pad, int(y1) - pad, int(x2) + pad, int(y2) + pad
    length = max(6, int(min(x2 - x1, y2 - y1) * 0.2))
    for cx, sx in ((x1, 1), (x2, -1)):
        for cy, sy in ((y1, 1), (y2, -1)):
            cv2.line(frame, (cx, cy), (cx + sx * length, cy), color, 2)
            cv2.line(frame, (cx, cy), (cx, cy + sy * length), color, 2)


def put_label(frame, text, org, color=ORANGE, scale=0.6):
    """Crisp label: dark anti-aliased outline + colored fill, readable on any background."""
    cv2.putText(frame, text, org, FONT, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, org, FONT, scale, color, 1, cv2.LINE_AA)


def draw_zones(frame, monitor) -> None:
    overlay = frame.copy()
    for name, polys in {**monitor.queues, **monitor.staff}.items():
        is_queue = name in monitor.queues
        count = monitor.counts.get(name, 0)
        over = is_queue and count >= monitor.min_people
        empty_staff = (not is_queue) and count == 0
        color = (0, 0, 255) if (over or empty_staff) else ((0, 165, 255) if is_queue else (0, 200, 0))
        for p in polys:
            cv2.fillPoly(overlay, [p], color)
    cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

    for name, polys in {**monitor.queues, **monitor.staff}.items():
        count = monitor.counts.get(name, 0)
        for p in polys:
            cv2.polylines(frame, [p], True, (255, 255, 255), 2)
        c = polys[0].mean(axis=0).astype(int)
        cv2.putText(frame, f"{name}: {count}", (int(c[0]) - 30, int(c[1])),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        # empty-staff timer on a white background (runs while the staff zone is empty)
        if name in monitor.staff and count == 0:
            draw_timer(frame, f"EMPTY {monitor.empty_time.get(name, 0.0):.1f}s",
                       (int(c[0]) - 40, int(c[1]) + 26))


def draw_timer(frame, text, org) -> None:
    scale, thick = 0.6, 2
    (w, h), _ = cv2.getTextSize(text, FONT, scale, thick)
    x, y = org
    cv2.rectangle(frame, (x - 4, y - h - 6), (x + w + 4, y + 6), (255, 255, 255), -1)
    cv2.putText(frame, text, (x, y), FONT, scale, ORANGE, thick, cv2.LINE_AA)


def draw_banner(frame, alerts) -> None:
    if not alerts:
        return
    text = "ALERT   " + "    ".join(alerts)
    (_, h), _ = cv2.getTextSize(text, FONT, 0.7, 2)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], h + 18), (0, 0, 200), -1)
    cv2.putText(frame, text, (14, h + 10), FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)


def gpu_mb() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_reserved() / 1e6
    except Exception:
        pass
    return 0.0


def draw_stats(frame, source, fps) -> None:
    put_label(frame, f"{source}  FPS {fps:4.1f}  GPU {gpu_mb():.0f}MB",
              (14, frame.shape[0] - 14), (0, 255, 0), 0.6)


def draw_tracks(frame, tracks, monitor, show_bbox, show_status) -> None:
    for x1, y1, x2, y2, track_id, *_ in tracks:
        x1, y1, x2, y2, tid = int(x1), int(y1), int(x2), int(y2), int(track_id)
        color = track_color(monitor, tid)                         # staff / queue / default
        if show_bbox:
            draw_corner_box(frame, x1, y1, x2, y2, color)         # 4-corner brackets
        cv2.circle(frame, ((x1 + x2) // 2, (y1 + y2) // 2), 4, color, -1)   # centre point
        if show_status:
            dwell = monitor.dwell.get(tid, 0.0)
            put_label(frame, f"[{tid}:{dwell:.1f}s]", (x1, y1 - 8), color)


def run_stream(video, show=True, save=None, bbox=False, status=False,
               loop=False, limit=0) -> None:
    """Process one source until it ends (loop=True -> reconnect and keep going)."""
    full = yaml.safe_load(CONFIG_PATH.read_text())
    source = Path(video).stem
    video_zones = (full.get("zones") or {}).get(source)
    if not video_zones:
        print(f"[{source}] no zones in config.yaml; skipping. Draw them with draw_zone.py")
        return
    cfg = {**full, "zones": video_zones,
           "roles": (full.get("roles") or {}).get(source, {}),
           "pairs": (full.get("pairs") or {}).get(source, [])}
    out = cfg.get("output", {})
    out_dir = (HERE / out.get("events_path", "output/events.jsonl")).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    detector, tracker = Detector(), Tracker()
    monitor = ZoneMonitor(source, cfg, out_dir / f"{source}_events.jsonl")
    recorder = QueueRecorder(source, monitor.queues, monitor.staff,
                             out.get("interval_sec", 60), out_dir / f"{source}_queue_minute.csv")

    writer, base_fps, frames = None, None, 0
    fps, fps_n, fps_t0, stop = 0.0, 0, time.monotonic(), False
    try:
        while not stop:
            cap = cv2.VideoCapture(video)
            if not cap.isOpened():
                print(f"[{source}] cannot open, retrying in 2s")
                time.sleep(2.0)
                continue
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 25
            base_fps = base_fps or src_fps
            target_dt = 1.0 / src_fps
            if save and writer is None:
                w, h = int(cap.get(3)), int(cap.get(4))
                writer = cv2.VideoWriter(save, cv2.VideoWriter_fourcc(*"mp4v"), 20, (w, h))
            print(f"[{source}] connected ({src_fps:.0f} fps)")

            while True:
                f0 = time.monotonic()
                ok, frame = cap.read()
                if not ok:
                    break
                frames += 1
                t = frames / base_fps                    # video-time timeline (seconds of footage)

                tracks = tracker.update(detector.detect(frame), frame)
                monitor.update(tracks, t)
                recorder.update(monitor.counts, t, 1.0 / base_fps)

                fps_n += 1
                now = time.monotonic()
                if now - fps_t0 >= 0.5:
                    fps, fps_n, fps_t0 = fps_n / (now - fps_t0), 0, now

                draw_zones(frame, monitor)
                draw_tracks(frame, tracks, monitor, bbox, status)
                draw_banner(frame, monitor.active_alerts())
                draw_stats(frame, source, fps)

                if writer:
                    writer.write(frame)
                if show:
                    cv2.imshow(source, frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        stop = True
                        break

                if limit and frames >= limit:
                    stop = True
                    break
                if loop:                                 # multi-stream service: play at real time
                    elapsed = time.monotonic() - f0
                    if elapsed < target_dt:
                        time.sleep(target_dt - elapsed)

            cap.release()
            if not loop:
                stop = True
            elif not stop:
                print(f"[{source}] source ended/dropped, reconnecting...")
                time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.close(frames / (base_fps or 25))
        recorder.close()
        if writer:
            writer.release()
        if show:
            cv2.destroyWindow(source)
        print(f"[{source}] stopped")


def main() -> None:
    ap = argparse.ArgumentParser(description="Queue / counter zone monitor (one or more sources).")
    ap.add_argument("--video", nargs="+", required=True, help="One or more full video paths.")
    ap.add_argument("--save", help="Single source: output file. Multi: output directory.")
    ap.add_argument("--bbox", action="store_true", help="Draw detection boxes.")
    ap.add_argument("--status", action="store_true", help="Show each track ID.")
    ap.add_argument("--no-show", action="store_true", help="Headless (no window).")
    args = ap.parse_args()
    show = not args.no_show

    if len(args.video) == 1:                              # single source: unchanged behaviour
        run_stream(args.video[0], show=show, save=args.save,
                   bbox=args.bbox, status=args.status, loop=False)
        cv2.destroyAllWindows()
        return

    procs = []                                           # multiple sources: one process each
    for v in args.video:
        save = str(Path(args.save) / f"{Path(v).stem}.mp4") if args.save else None
        p = mp.Process(target=run_stream, args=(v, show, save, args.bbox, args.status, True))
        p.start()
        procs.append(p)
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)             # required for CUDA in subprocesses
    main()
