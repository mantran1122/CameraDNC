"""Person-first yellow/blue uniform detection for the admissions live camera."""
from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np
from PIL import Image


class YellowUniformDetector:
    """Detect people with YOLO, then classify only their upper-body colour."""

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(os.getenv("STAFF_DETECTOR_MODEL", "yolo11n.pt"))
        return self._model

    @staticmethod
    def _uniform_scores(person_bgr: np.ndarray) -> tuple[float, float]:
        height = person_bgr.shape[0]
        width = person_bgr.shape[1]
        # Keep the central upper body. Excluding box edges and the lower body
        # reduces yellow tables/chairs leaking into a seated person's score.
        top = int(height * 0.14)
        bottom = max(top + 1, int(height * 0.68))
        left = int(width * 0.14)
        right = max(left + 1, int(width * 0.86))
        torso = person_bgr[top:bottom, left:right]
        if torso.size == 0:
            return 0.0, 0.0
        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        yellow = cv2.inRange(hsv, (18, 80, 100), (42, 255, 255))
        blue = cv2.inRange(hsv, (90, 45, 35), (135, 255, 255))
        total = float(torso.shape[0] * torso.shape[1])
        return float(np.count_nonzero(yellow) / total), float(np.count_nonzero(blue) / total)

    def detect(self, image: Image.Image) -> dict[str, Any]:
        rgb = np.asarray(image)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        result = self._get_model().predict(
            source=bgr,
            classes=[0],  # COCO class 0: person
            conf=float(os.getenv("STAFF_PERSON_CONFIDENCE", "0.18")),
            imgsz=int(os.getenv("STAFF_DETECTOR_IMAGE_SIZE", "1280")),
            device=os.getenv("STAFF_DETECTOR_DEVICE", "cpu"),
            verbose=False,
        )[0]

        people = 0
        yellow_staff = 0
        yellow_min = float(os.getenv("STAFF_YELLOW_RATIO", "0.055"))
        blue_min = float(os.getenv("STAFF_BLUE_RATIO", "0.003"))
        yellow_only_min = float(os.getenv("STAFF_YELLOW_ONLY_RATIO", "0.16"))
        for x1, y1, x2, y2 in result.boxes.xyxy.cpu().numpy().astype(int):
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(bgr.shape[1], x2), min(bgr.shape[0], y2)
            if x2 - x1 < 10 or y2 - y1 < 20:
                continue
            people += 1
            yellow_ratio, blue_ratio = self._uniform_scores(bgr[y1:y2, x1:x2])
            if yellow_ratio >= yellow_min and (
                blue_ratio >= blue_min or yellow_ratio >= yellow_only_min
            ):
                yellow_staff += 1

        return {
            "people_detected": people,
            "yellow_uniform_staff": yellow_staff,
            "method": "yolo_person_upper_body_colour",
        }
