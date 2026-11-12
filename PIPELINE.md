# Door counting

Detect and track people, count them crossing a doorway, and write a per-window
CSV. Everything is driven by `configs/counting.yaml`.

```
   video frame
        │
        ▼
   YOLO detector        →  person boxes
        │
        ▼
   BoT-SORT tracker     →  people with stable ids
        │
        ▼
   two-line crossing    →  who crossed IN / OUT
        │
        ├─► IN / OUT totals   →  on-screen counter, incoming faces blurred
        └─► per-window CSV    →  in, out, occupancy, dwell per source
```

## Files

| File | Role |
|------|------|
| `draw_line.py` | draw the two counting lines on a video |
| `src/detector.py` | YOLO person detector |
| `src/tracker.py` | BoT-SORT tracker |
| `src/counter.py` | `DualLineCounter` — two-line IN/OUT |
| `src/recorder.py` | per-window CSV |
| `inference.py` | runs it, draws the view, saves |
| `run.sh` | one-command setup + run |

## Drawing the lines

```
python draw_line.py --video /path/to/video.mp4
```

Click two points per line (the outer line first, then the inner one), `s` to
save, `z` undo, `r` reset, `q` quit. The counter sorts them by height, so order
doesn't matter.

## Running

```
./run.sh                               # default video
python inference.py --video a.mp4 [--save out.mp4] [--bbox] [--status]
```

`--status` shows each person's zone, `--bbox` draws corner boxes, `--save`
writes an annotated video. Incoming people's boxes are blurred.

## Config

```yaml
counting:
  lines: [[[x,y],[x,y]], [[x,y],[x,y]]]   # outer + inner line
  confirm_frames: 3   # frames a zone must hold before it counts (debounce)
  cooldown: 25        # frames an id is locked after a count
  min_age: 5          # frames a track must exist before it can count
  min_travel: 30      # pixels the foot must have moved before it can count
recording:
  csv_path, interval_sec, dwell_threshold_sec
```

## How IN / OUT is decided

A person is tracked by its foot point (box bottom-centre). The two lines and
their side edges split the view into four zones; the **span** (between the side
edges) is tested first, so anything left or right of it is ELSEWHERE at any
height:

```
      ELSEWHERE │   OUT_ZONE   │ ELSEWHERE     (above outer, inside span)
                ╞══ outer line ═╡
      ELSEWHERE │     BAND     │ ELSEWHERE     (between lines, inside span)
                ╞══ inner line ═╡
      ELSEWHERE │   IN_ZONE    │ ELSEWHERE     (below inner, inside span)
```

Because OUT_ZONE / IN_ZONE live only inside the span, reaching one from the BAND
means crossing the **finite** line between its endpoints. The zone must hold for
`confirm_frames` before it is confirmed (debounce).

Direction comes from the **entry gate** — which side the person entered the BAND
from — and a count fires only on a real transit through the band:

```
enter BAND from OUT_ZONE, leave to IN_ZONE   → IN
enter BAND from IN_ZONE,  leave to OUT_ZONE  → OUT
enter from the side (ELSEWHERE), leave to IN / OUT_ZONE → IN / OUT
leave to ELSEWHERE, or stop / turn back / walk along the line → nothing
```

Guards: a count also needs `min_age` and `min_travel`, and an id is locked for
`cooldown` after it counts, so nobody is counted twice.

## Output

One CSV row per source every `interval_sec`:

```
source, window_start_s, in, out, occupancy, max_dwell_s, max_dwell_id, loiter
```

`occupancy` is the running inside count; `max_dwell_s` is the longest a single
person stayed near the doorway in the window, and `loiter` flags when that
reaches `dwell_threshold_sec`. Times are in video seconds.

## Notes

- Counting uses the foot point; a steep overhead angle suits it best.
- Track ids are not reproducible run-to-run (GPU / tracker); debug by trajectory.
