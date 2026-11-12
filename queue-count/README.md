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

| t (s) | service_1 hand | service_1 sys | service_2 hand | service_2 sys | service_3 hand | service_3 sys |
|------:|---------------:|--------------:|---------------:|--------------:|---------------:|--------------:|
| 10    | – | – | – | – | – | – |
| 20    | – | – | – | – | – | – |
| 30    | – | – | – | – | – | – |
| 40    | – | – | – | – | – | – |
| 50    | – | – | – | – | – | – |
| **MAE** | | – | | – | | – |

### Alerts

List the alerts you expect from the clip by hand, then report how many the
system **found**, **missed**, and **raised wrongly** (false alerts).

| Alert type | Expected (hand) | Found | Missed | False |
|------------|----------------:|------:|-------:|------:|
| queue_alert | – | – | – | – |
| empty_counter | – | – | – | – |

## Results

Annotated output videos are in `results/` after running `./download_videos.sh`:

- `results/supermarket_demo_out.mp4`
- `results/cctv_demo1_out.mp4`

## Screenshots

![zones and counts](assets/view_counts.png)

![alert banner](assets/view_alert.png)

## Architecture

Each person is placed in one zone, which gives the per-zone counts, a waiting
timer, the queue and empty-counter alerts, and the per-minute CSV.

Full method and flowchart: [PIPELINE.md](PIPELINE.md)
