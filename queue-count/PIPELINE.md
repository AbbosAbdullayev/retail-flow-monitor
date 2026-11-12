# Queue / counter zone monitoring

This module takes the tracks from the main pipeline (`../src/detector.py`,
`../src/tracker.py`) and works out who is standing in each zone, how long they
wait, and when to raise an alert. Everything is driven by `config.yaml`.

```
   video frame
        │
        ▼
   YOLO detector            →  person boxes
        │
        ▼
   BoT-SORT tracker         →  people with stable ids
        │
        ▼
   zone membership          →  who is in each queue / staff zone
        │
        ├─► counts + waiting time   →  on-screen labels + red alert banner
        ├─► queue / empty alerts    →  <source>_events.jsonl
        └─► per-minute averages     →  <source>_queue_minute.csv
```

## Files

| File | Role |
|------|------|
| `draw_zone.py` | draw the polygon zones for a video |
| `monitor.py`   | zone membership, waiting time, alerts |
| `recorder.py`  | per-minute CSV |
| `run.py`       | runs one or more sources and draws the view |
| `run.sh`       | one-command setup + run |

## Drawing zones

```
python draw_zone.py --video /path/to/video.mp4
```

Loops through that video's `zone_names`: click the polygon, `n` next, `b` back,
`s` save, `z` undo, `r` reset, `q` quit. A zone may have several polygons. If the
video already has zones it opens in view mode — press `c` to redraw.

## Running

```
./run.sh                              # default source
python run.py --video a.mp4           # one source, full speed
python run.py --video a.mp4 b.mp4     # several sources at once, real-time, auto-reconnect
```

Flags: `--bbox`, `--status`, `--save`, `--no-show`. Each source writes its own
CSV and events file.

## Config

Zones, their names, roles and pairing are kept **per video** (keyed by the file
name without `.mp4`); the thresholds are shared.

```yaml
zone_names:                         # draw order, per video
  supermarket_demo: [service_1, ..., staff_1, ...]
zones:                              # polygons, per video (filled by draw_zone.py)
  supermarket_demo:
    service_1: [ [[x,y],...] ]      # a zone is a list of polygons
roles:                              # which zones are queues vs staff, per video
  supermarket_demo: { queue: [...], counter: [...] }
pairs:                              # staff<->queue pairing, per video
  supermarket_demo: [ [service_2, staff_1], ... ]
counting: { box, overlap, enter_seconds, exit_seconds, grace_seconds, stay }
alerts:   { queue_alert: {min_people, for_seconds}, empty_counter: {for_seconds}, release_seconds }
output:   { events_path, csv_path, interval_sec }
```

## Who is in a zone

Each track is placed in at most one zone. The decision is per frame but
confirmed over time, so the counts stay steady:

1. The track's anchor is the **bounding-box centre**.
2. A small `box`×`box` patch around the centre is sampled on a grid; a zone is a
   candidate when more than `overlap` of the patch falls inside it.
3. If several zones qualify, the one with the most coverage wins, and a tie
   keeps the current zone — so a person on a shared border is never counted
   twice.
4. A track **joins** a zone once the patch supports it for `enter_seconds`, and
   **leaves** once it is unsupported for `exit_seconds`.
5. While leaving, if the centre is in no zone but the whole box still covers the
   old zone by more than `stay`, the track is held until the box clears.
6. If a track id briefly disappears (a detection gap), its state is kept for
   `grace_seconds` instead of being dropped.

`counts[zone]` is the number of tracks assigned to that zone.

## Waiting time

A per-track timer counts up while the track stays in its queue, restarts if it
moves to a different queue, and freezes when it leaves. It shows as `[id:time]`.

## Alerts

An alert fires once its condition has held for `for_seconds`, remembers the peak
while active, and clears only after the condition stays false for
`release_seconds` — so each event is recorded once, without flickering.

- **Queue alert** — at least `min_people` in a queue for `for_seconds`.
- **Empty-counter alert** — a staff zone empty for `for_seconds` while its paired
  queue has someone.

Events go to `output/<source>_events.jsonl`, one JSON object per event:

```json
{"source": "...", "type": "queue_alert",   "zone": "service_2", "start": 12.0, "end": 41.0, "peak": 4}
{"source": "...", "type": "empty_counter", "zone": "staff_1",  "start": 92.6, "end": 104.5, "peak": 1, "queue": "service_3"}
```

An active alert also shows as a red banner at the top of the window.

## Per-minute CSV

`output/<source>_queue_minute.csv`, one row per `interval_sec` of video:

```
source, minute_start, avg_<queue>, max_<queue> ..., empty_<staff>_s ...
```

Times are in video seconds (frame count ÷ fps), so the rows line up with the
footage no matter how fast it processes.
