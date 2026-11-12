"""Writes the per-minute CSV: average and peak queue occupancy, and the
seconds each staff zone was empty, one row per source per interval."""
from __future__ import annotations

import csv
from pathlib import Path


class QueueRecorder:
    """One CSV row per source every `interval_sec`: avg/max queue, empty seconds."""

    def __init__(self, source: str, queues, staff, interval_sec: float, csv_path: Path):
        self.source = source
        self.queues = list(queues)
        self.staff = list(staff)
        self.interval = interval_sec
        self.path = Path(csv_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        cols = ["source", "minute_start"]
        for q in self.queues:
            cols += [f"avg_{q}", f"max_{q}"]
        for s in self.staff:
            cols += [f"empty_{s}_s"]
        with self.path.open("w", newline="") as f:
            csv.writer(f).writerow(cols)

        self._win_start = 0.0
        self._reset()

    def _reset(self) -> None:
        self._dur = 0.0
        self._area = {q: 0.0 for q in self.queues}      # integral of count*dt
        self._max = {q: 0 for q in self.queues}
        self._empty = {s: 0.0 for s in self.staff}

    def update(self, counts: dict, t: float, dt: float) -> None:
        self._dur += dt
        for q in self.queues:
            c = counts.get(q, 0)
            self._area[q] += c * dt
            self._max[q] = max(self._max[q], c)
        for s in self.staff:
            if counts.get(s, 0) == 0:
                self._empty[s] += dt
        if t - self._win_start >= self.interval:
            self._flush()
            self._win_start = t
            self._reset()

    def _flush(self) -> None:
        dur = self._dur or 1e-9
        row = [self.source, round(self._win_start, 1)]
        for q in self.queues:
            row += [round(self._area[q] / dur, 2), self._max[q]]
        for s in self.staff:
            row += [round(self._empty[s], 1)]
        with self.path.open("a", newline="") as f:
            csv.writer(f).writerow(row)

    def close(self) -> None:
        if self._dur > 0:
            self._flush()
