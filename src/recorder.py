from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = ["source", "window_start_s", "in", "out", "occupancy",
           "max_dwell_s", "max_dwell_id", "loiter"]


class Recorder:
    """Writes one CSV row per source every `interval_sec` seconds.

    Columns: source, window start (video seconds), IN and OUT in the window,
    occupancy (running inside), the longest a single person stayed in BAND/IN
    during the window (seconds) and its track id, and `loiter` = that dwell
    reached `dwell_threshold_sec` (informative only, no alert raised).
    """

    def __init__(self, source: str, fps: float, cfg: dict):
        self.source = source
        self.fps = fps or 25
        self.interval = int(cfg.get("interval_sec", 30) * self.fps)
        self.dwell_limit = cfg.get("dwell_threshold_sec", 10) * self.fps
        self.path = Path(cfg.get("csv_path", "output/counts.csv"))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="") as f:
            csv.writer(f).writerow(COLUMNS)

        self.frame = 0
        self.win_start = 0
        self.prev_in = 0
        self.prev_out = 0
        self.dwell: dict[int, int] = {}      # track_id -> consecutive frames in BAND/IN
        self.peak_frames = 0
        self.peak_id = -1

    def update(self, tracks, counter) -> None:
        self.frame += 1
        dwell = {}
        for t in tracks:
            tid = int(t[4])
            d = self.dwell.get(tid, 0) + 1 if counter.status(tid) in ("BAND", "IN") else 0
            dwell[tid] = d
            if d > self.peak_frames:
                self.peak_frames, self.peak_id = d, tid
        self.dwell = dwell

        if self.frame - self.win_start >= self.interval:
            self._flush(counter)

    def _flush(self, counter) -> None:
        with self.path.open("a", newline="") as f:
            csv.writer(f).writerow([
                self.source,
                round(self.win_start / self.fps, 1),
                counter.in_count - self.prev_in,
                counter.out_count - self.prev_out,
                counter.in_count - counter.out_count,
                round(self.peak_frames / self.fps, 1),
                self.peak_id,
                self.peak_frames >= self.dwell_limit,
            ])
        self.prev_in = counter.in_count
        self.prev_out = counter.out_count
        self.win_start = self.frame
        self.peak_frames, self.peak_id = 0, -1

    def close(self, counter) -> None:
        if self.frame > self.win_start:      # flush the final partial window
            self._flush(counter)
