from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from boxmot import BotSort

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "counting.yaml"


class Tracker:
    """Wraps BoT-SORT (motion + ReID) and assigns stable IDs to detections.

    update(detections, frame) -> np.ndarray of shape (M, 8):
        [x1, y1, x2, y2, track_id, conf, cls, det_index]
    `detections` is the (N, 6) array returned by Detector.detect().
    """

    def __init__(self):
        cfg = yaml.safe_load(CONFIG_PATH.read_text())["tracking"]
        self.tracker = BotSort(
            reid_weights=Path(cfg["reid_weights"]),
            device=cfg["device"],
            half=cfg["half"],
            with_reid=cfg["with_reid"],
            cmc_method=cfg.get("cmc_method", "sof"),
            track_buffer=cfg["track_buffer"],
            match_thresh=cfg["match_thresh"],
            track_high_thresh=cfg["track_high_thresh"],
            track_low_thresh=cfg["track_low_thresh"],
            new_track_thresh=cfg["new_track_thresh"],
        )

    def update(self, detections: np.ndarray, frame: np.ndarray) -> np.ndarray:
        return self.tracker.update(detections, frame)
