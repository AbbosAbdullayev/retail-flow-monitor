from __future__ import annotations

import numpy as np

OUT_ZONE = "out_zone"
BAND = "band"
IN_ZONE = "in_zone"
ELSEWHERE = "elsewhere"


class DualLineCounter:
    """Counts IN/OUT with two finite lines, span-restricted.

    The two lines (outer = upper, inner = lower) and their side edges bound a
    BAND. The span (between the two side edges) is tested first, so anything
    left/right of it is ELSEWHERE at any height. Inside the span, above the
    outer line is OUT_ZONE and below the inner line is IN_ZONE. Reaching
    OUT_ZONE / IN_ZONE from the BAND therefore requires crossing the finite
    line segment between its endpoints: a person who leaves the BAND sideways
    and rises past an endpoint stays in ELSEWHERE and is never counted.

    A person is tracked by its foot point (box bottom-center); its zone must
    hold for `confirm_frames` to count (debounce). Direction comes from the
    entry gate (which zone it entered the BAND from):
        reach IN_ZONE  and entry gate != INNER  -> IN
        reach OUT_ZONE and entry gate != OUTER  -> OUT
    Guards: a track must pass `min_age` and `min_travel`, and an ID is in
    `cooldown` after a count so it is not counted twice.
    """

    def __init__(self, lines, confirm_frames=3, cooldown=25, min_age=5, min_travel=30):
        # Outer = upper line (smaller avg y); endpoints ordered left-to-right.
        up, down = sorted(lines, key=lambda ln: (ln[0][1] + ln[1][1]) / 2)
        up = sorted(up, key=lambda p: p[0])
        down = sorted(down, key=lambda p: p[0])
        self.lines = {"up": up, "down": down}

        cx = sum(p[0] for p in up + down) / 4      # band centre
        cy = sum(p[1] for p in up + down) / 4
        self._out_side = -self._which_side(up, cx, cy)       # beyond the outer line
        self._in_side = -self._which_side(down, cx, cy)      # beyond the inner line
        self._left = [up[0], down[0]]
        self._right = [up[1], down[1]]
        self._left_in = self._which_side(self._left, cx, cy)
        self._right_in = self._which_side(self._right, cx, cy)

        self.confirm_frames = confirm_frames
        self.cooldown = cooldown
        self.min_age = min_age
        self.min_travel = min_travel

        self.in_count = 0
        self.out_count = 0
        self._frame = 0
        self._state: dict[int, dict] = {}

    @staticmethod
    def _which_side(line, x, y) -> int:
        """Which side of the line the point is on: +1, -1, or 0 (on it)."""
        (ax, ay), (bx, by) = line
        return int(np.sign((bx - ax) * (y - ay) - (by - ay) * (x - ax)))

    def _within_span(self, x, y) -> bool:
        sl = self._which_side(self._left, x, y)
        sr = self._which_side(self._right, x, y)
        return sl in (0, self._left_in) and sr in (0, self._right_in)

    def _region(self, x, y) -> str:
        if not self._within_span(x, y):
            return ELSEWHERE                   # left/right of the span (any height)
        if self._which_side(self.lines["up"], x, y) == self._out_side:
            return OUT_ZONE                    # above the outer line, inside the span
        if self._which_side(self.lines["down"], x, y) == self._in_side:
            return IN_ZONE                     # below the inner line, inside the span
        return BAND                            # between the lines, inside the span

    def update(self, tracks: np.ndarray) -> tuple[int, int]:
        self._frame += 1
        for x1, y1, x2, y2, track_id, *_ in tracks:
            tid = int(track_id)
            foot = ((x1 + x2) / 2, y2)

            st = self._state.get(tid)
            if st is None:
                st = self._state[tid] = {
                    "raw": None, "raw_n": 0, "region": None,
                    "gate": None, "age": 0, "p0": foot, "cooldown_until": 0,
                }
            st["age"] += 1

            raw = self._region(*foot)
            if raw == st["raw"]:
                st["raw_n"] += 1
            else:
                st["raw"], st["raw_n"] = raw, 1

            if st["raw_n"] >= self.confirm_frames and raw != st["region"]:
                self._on_change(st, st["region"], raw, foot)
                st["region"] = raw
        return self.in_count, self.out_count

    def _on_change(self, st, prev, new, foot) -> None:
        if prev is None:                      # first confirmed region: just set up
            st["gate"] = "SIDE" if new == BAND else None
            return
        if new == BAND:                       # entering the band: remember from where
            st["gate"] = {OUT_ZONE: "OUTER", IN_ZONE: "INNER"}.get(prev, "SIDE")
            return
        # A zone only counts via a real transit THROUGH the band (crossing the
        # finite line). Arriving from ELSEWHERE or by a side route never counts.
        if new == IN_ZONE:
            if prev == BAND and st["gate"] != "INNER":
                self._try_count(st, "in", foot)
        elif new == OUT_ZONE:
            if prev == BAND and st["gate"] != "OUTER":
                self._try_count(st, "out", foot)
        st["gate"] = None                     # close the visit (incl. ELSEWHERE)

    def _try_count(self, st, direction, foot) -> None:
        if self._frame < st["cooldown_until"]:
            return
        if st["age"] < self.min_age:
            return
        travel = ((foot[0] - st["p0"][0]) ** 2 + (foot[1] - st["p0"][1]) ** 2) ** 0.5
        if travel < self.min_travel:
            return
        if direction == "in":
            self.in_count += 1
        else:
            self.out_count += 1
        st["cooldown_until"] = self._frame + self.cooldown

    def is_entering(self, track_id) -> bool:
        st = self._state.get(int(track_id))
        return bool(st and st["gate"] == "OUTER")

    def status(self, track_id) -> str:
        """Current confirmed zone of a track, as a short label."""
        st = self._state.get(int(track_id))
        label = {OUT_ZONE: "OUT", BAND: "BAND", IN_ZONE: "IN", ELSEWHERE: "ELSE"}
        return label.get(st["region"], "-") if st else "-"
