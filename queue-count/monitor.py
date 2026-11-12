"""Decides who is in each zone, measures waiting time, and raises the
queue / empty-counter alerts. Reads tracks, writes alert events as JSON."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

GRID = 7                                   # NxN samples across the patch -> overlap fraction


def _polys(areas) -> list[np.ndarray]:
    return [np.array(a, np.int32) for a in areas]


def _overlap(center, box, polys) -> float:
    """Fraction of a box x box patch at `center` that falls inside any polygon."""
    cx, cy = center
    h = box / 2.0
    return _grid_fraction(cx - h, cy - h, cx + h, cy + h, polys)


def _bbox_coverage(bbox, polys) -> float:
    """Fraction of the whole bounding box that falls inside any polygon."""
    x1, y1, x2, y2 = bbox
    return _grid_fraction(x1, y1, x2, y2, polys)


def _grid_fraction(x1, y1, x2, y2, polys) -> float:
    hits = 0
    for x in np.linspace(x1, x2, GRID):
        for y in np.linspace(y1, y2, GRID):
            if any(cv2.pointPolygonTest(p, (float(x), float(y)), False) >= 0 for p in polys):
                hits += 1
    return hits / (GRID * GRID)


class Alert:
    """Fires once after the condition holds for `hold` seconds, and clears once
    it stays false for `release` seconds. Returns one event (start, end, peak)
    when it clears, so brief spikes and detection gaps do not make it flicker.
    """

    def __init__(self, kind: str, zone: str, hold: float, release: float):
        self.kind, self.zone = kind, zone
        self.hold, self.release = hold, release
        self.on = False
        self.true_since: float | None = None
        self.false_since: float | None = None
        self.start: float | None = None
        self.peak = 0

    def update(self, t: float, condition: bool, value: int) -> dict | None:
        if condition:
            self.false_since = None
            if self.true_since is None:
                self.true_since = t
            if not self.on and t - self.true_since >= self.hold:
                self.on, self.start, self.peak = True, self.true_since, value
            if self.on:
                self.peak = max(self.peak, value)
            return None

        self.true_since = None
        if self.on:
            if self.false_since is None:
                self.false_since = t
            if t - self.false_since >= self.release:
                return self._close(t)
        return None

    def _close(self, t: float) -> dict:
        ev = {"type": self.kind, "zone": self.zone,
              "start": round(self.start, 1), "end": round(t, 1), "peak": self.peak}
        self.on, self.start, self.false_since = False, None, None
        return ev

    def flush(self, t: float) -> dict | None:
        return self._close(t) if self.on else None


class ZoneMonitor:
    """Tracks who is in each zone and raises queue / empty-counter alerts."""

    def __init__(self, source: str, cfg: dict, events_path: Path):
        zones = cfg["zones"]
        roles = cfg.get("roles", {})
        self.queues = {q: _polys(zones[q]) for q in roles.get("queue", []) if zones.get(q)}
        self.staff = {c: _polys(zones[c]) for c in roles.get("counter", []) if zones.get(c)}

        a = cfg["alerts"]
        self.min_people = a["queue_alert"]["min_people"]
        rel = a.get("release_seconds", 1)
        self.queue_alerts = {q: Alert("queue_alert", q, a["queue_alert"]["for_seconds"], rel)
                             for q in self.queues}
        self.empty_alerts = {}                        # counter -> (Alert, paired queue)
        for q, c in cfg.get("pairs", []):
            if q in self.queues and c in self.staff:
                self.empty_alerts[c] = (Alert("empty_counter", c, a["empty_counter"]["for_seconds"], rel), q)

        c = cfg.get("counting", {})
        self.box = c.get("box", 30)                   # central patch side (px)
        self.overlap_thr = c.get("overlap", 0.51)     # patch fraction inside a zone to count
        self.enter_s = c.get("enter_seconds", 0.4)    # dwell needed to confirm entry
        self.exit_s = c.get("exit_seconds", 0.5)      # dwell needed to confirm exit
        self.grace = c.get("grace_seconds", 0.6)      # keep state this long when the ID drops out
        self.stay = c.get("stay", 0.20)               # bbox-coverage exit guard threshold

        self.counts: dict[str, int] = {}
        self.dwell: dict[int, float] = {}             # track_id -> seconds in its CURRENT queue zone
        self.empty_time: dict[str, float] = {}        # staff zone -> seconds currently empty
        self._last_t = 0.0
        self._st: dict[int, dict] = {}                # track_id -> {zone, cand, enter_t, exit_t}
        self._dwell_zone: dict[int, str] = {}         # track_id -> the queue its dwell belongs to
        self._last_seen: dict[int, float] = {}        # track_id -> time last present
        self.events_path = Path(events_path)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.events_path.open("w")
        self.source = source

    def update(self, tracks, t: float) -> None:
        dt = t - self._last_t
        self._last_t = t
        all_zones = {**self.queues, **self.staff}

        present = set()
        for x1, y1, x2, y2, track_id, *_ in tracks:
            tid = int(track_id)
            present.add(tid)
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            cov = {z: _overlap(center, self.box, polys) for z, polys in all_zones.items()}
            cand = [z for z in all_zones if cov[z] > self.overlap_thr]

            st = self._st.get(tid)
            if st is None:
                st = self._st[tid] = {"zone": None, "cand": None, "enter_t": 0.0, "exit_t": 0.0}
            zone = st["zone"]
            # exclusive: one zone per ID = highest coverage; a tie keeps the current zone
            pick = (zone if zone in cand else max(cand, key=lambda z: cov[z])) if cand else None

            if zone is None:                           # entry: patch must support a zone for enter_s
                if pick is not None:
                    st["enter_t"] = st["enter_t"] + dt if st["cand"] == pick else dt
                    st["cand"] = pick
                    if st["enter_t"] >= self.enter_s:
                        st.update(zone=pick, cand=None, enter_t=0.0, exit_t=0.0)
                else:
                    st["cand"], st["enter_t"] = None, 0.0
            else:                                      # exit: must be unsupported for exit_s
                supported = pick == zone
                if not supported and pick is None \
                        and _bbox_coverage((x1, y1, x2, y2), all_zones[zone]) > self.stay:
                    supported = True                   # exit guard: whole box still covers the zone
                if supported:
                    st["exit_t"] = 0.0
                else:
                    st["exit_t"] += dt
                    if st["exit_t"] >= self.exit_s:
                        st.update(zone=None, exit_t=0.0)
                        if pick is not None:           # immediately start entering the new zone
                            st["cand"], st["enter_t"] = pick, dt

            z = st["zone"]                             # per-queue dwell
            if z in self.queues:                       # inside a queue: count up (fresh on a new visit)
                self.dwell[tid] = self.dwell.get(tid, 0.0) + dt if self._dwell_zone.get(tid) == z else dt
                self._dwell_zone[tid] = z
            else:                                      # left the queue: STOP the timer (freeze its value)
                self._dwell_zone[tid] = None
            self._last_seen[tid] = t

        # tracks absent this frame: keep (freeze) within the grace period, else forget
        for tid in list(self._st):
            if tid not in present and t - self._last_seen.get(tid, t) > self.grace:
                for d in (self._st, self.dwell, self._dwell_zone, self._last_seen):
                    d.pop(tid, None)

        self.counts = {z: sum(1 for st in self._st.values() if st["zone"] == z) for z in all_zones}

        # staff empty-timer: counts up while the zone is empty
        for s in self.staff:
            self.empty_time[s] = self.empty_time.get(s, 0.0) + dt if self.counts[s] == 0 else 0.0

        qc = {q: self.counts[q] for q in self.queues}
        sc = {s: self.counts[s] for s in self.staff}
        for q, alert in self.queue_alerts.items():
            ev = alert.update(t, qc[q] >= self.min_people, qc[q])
            if ev:
                self._emit(ev)
        for s, (alert, q) in self.empty_alerts.items():
            ev = alert.update(t, sc[s] == 0 and qc[q] >= 1, qc[q])
            if ev:
                self._emit({**ev, "queue": q})

    def zone_of(self, track_id):
        """The single zone a track is currently assigned to (or None)."""
        st = self._st.get(int(track_id))
        return st["zone"] if st else None

    def active_alerts(self) -> list[str]:
        """Labels for alerts currently firing (for the on-screen banner)."""
        labels = [f"QUEUE {q}" for q, al in self.queue_alerts.items() if al.on]
        labels += [f"STAFF EMPTY {s}" for s, (al, _) in self.empty_alerts.items() if al.on]
        return labels

    def _emit(self, ev: dict) -> None:
        self._fh.write(json.dumps({"source": self.source, **ev}) + "\n")
        self._fh.flush()
        print("ALERT", ev)

    def close(self, t: float) -> None:
        for alert in self.queue_alerts.values():
            ev = alert.flush(t)
            if ev:
                self._emit(ev)
        for alert, q in self.empty_alerts.values():
            ev = alert.flush(t)
            if ev:
                self._emit({**ev, "queue": q})
        self._fh.close()
