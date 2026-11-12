# Queue / Counter Zone Monitoring

Counts how many people wait in each queue zone, checks whether a staff member is
at each counter, and raises queue and empty-counter alerts. Runs one or more
camera sources at once. Built on YOLO detection + BoT-SORT tracking.

## Download the videos

The evaluation clips (and the annotated result videos) are hosted on Google
Drive. Fetch them all with:

```
./download_videos.sh
```

Input clips land in `videos/`, output videos in `results/`.

## Running

| Command | Runs |
|---------|------|
| `./run.sh` | `run.py --video ./videos/supermarket_demo.mp4 --status` (default) |
| `./run.sh --bbox` | default + `--bbox` |
| `./run.sh --video a.mp4 b.mp4` | your sources, multi-stream (exactly like `run.py`) |

`run.sh` creates the virtual environment, fetches the model weights, checks the
zones are drawn, then runs. Each source writes
`output/<source>_queue_minute.csv` and `output/<source>_events.jsonl`.

## Accuracy

Clip: `supermarket_demo` (fill the dashes after labeling; they mark what to
measure, not a claimed score). Door IN/OUT accuracy is measured in the
people-counting section, not here.

### Queue occupancy

Hand-label the number of people in each queue zone **every 10 seconds for at
least 2 minutes**, read the system's count at the same timestamps, and report
the **mean absolute error (MAE)** per zone.

| t (s) | service_2 hand | service_2 sys | service_3 hand | service_3 sys |
|------:|---------------:|--------------:|---------------:|--------------:|
| 0     | – | – | – | – |
| 10    | – | – | – | – |
| …     | – | – | – | – |
| 120   | – | – | – | – |
| **MAE** | | – | | – |

### Alerts

List the alerts you expect from the clip by hand, then report how many the
system **found**, **missed**, and **raised wrongly** (false alerts).

| Alert type | Expected (hand) | Found | Missed | False |
|------------|----------------:|------:|-------:|------:|
| queue_alert | – | – | – | – |
| empty_counter | – | – | – | – |

## Results

Annotated output videos (zones, counts, `[id:time]`, alert banner) are in
`results/` after running `download.py`:

- `results/supermarket_demo_out.mp4`
- `results/cctv_demo1_out.mp4`

You can also regenerate them locally with `--save`, e.g.
`python run.py --video ./videos/supermarket_demo.mp4 --status --save results/supermarket_demo_out.mp4`.

## Screenshots

<p>
  <img src="assets/view_counts.png" width="49%"/>
  <img src="assets/view_alert.png" width="49%"/>
</p>

## Architecture

Each camera is run through YOLO detection and BoT-SORT tracking. A track is
assigned to at most one zone from the overlap of a patch at its box centre,
confirmed over a short enter/exit time, with an exit guard and a grace period for
dropped ids. From the memberships the system produces per-zone counts, a waiting
timer per person, queue / empty-counter alerts, and a per-minute CSV.

Full method and flowchart: [PIPELINE.md](PIPELINE.md).
