from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from ultralytics import YOLO

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "counting.yaml"


class Detector:
    """Runs a YOLO person detector and returns boxes as a plain array.

    detect() -> np.ndarray of shape (N, 6): [x1, y1, x2, y2, conf, cls]
    """

    def __init__(self):
        self.cfg = yaml.safe_load(CONFIG_PATH.read_text())["detection"]
        self.model = YOLO(self.cfg["weights"])

    def detect(self, frame: np.ndarray) -> np.ndarray:
        result = self.model.predict(
            frame,
            conf=self.cfg["conf"],
            iou=self.cfg["iou"],
            classes=self.cfg["classes"],
            imgsz=self.cfg["imgsz"],
            device=self.cfg["device"],
            verbose=False,
        )[0]

        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return np.empty((0, 6), dtype=np.float32)

        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()[:, None]
        cls = boxes.cls.cpu().numpy()[:, None]
        return np.hstack((xyxy, conf, cls)).astype(np.float32)
