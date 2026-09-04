"""Manual background analysis of representative frames from an event clip."""

import queue
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import cv2
import requests

import config
import database
from clip_storage import resolve_clip_path


_RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


class VideoAnalysisWorker:
    def __init__(self, on_updated: Optional[Callable[[int], None]] = None):
        self._on_updated = on_updated
        self._queue: queue.Queue[Optional[int]] = queue.Queue()
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="video-analysis-worker")
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def enqueue(self, event_id: int) -> None:
        if not self._thread or not self._thread.is_alive():
            self.start()
        print(f"[VIDEO AI] alert={event_id} analysis requested")
        self._queue.put(event_id)

    def _run(self) -> None:
        while self._running.is_set():
            try:
                event_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if event_id is None:
                continue
            try:
                self._process(event_id)
            except Exception as exc:
                print(f"[VIDEO AI] alert={event_id} failed: {exc}")
                self._set_status(event_id, "failed", error_message=str(exc))

    def _set_status(self, event_id: int, status: str, **values) -> None:
        database.update_video_analysis(event_id, status=status, **values)
        if self._on_updated:
            self._on_updated(event_id)

    def _process(self, event_id: int) -> None:
        event = database.get_event_by_id(event_id)
        if not event:
            return
        saved_clip = str(event.get("clip_filename") or "")
        clip_path = resolve_clip_path(saved_clip) if saved_clip else None
        if clip_path is None or not clip_path.is_file():
            self._set_status(event_id, "video_missing", error_message="Không tìm thấy video evidence của cảnh báo.")
            return

        self._set_status(event_id, "extracting_frames", error_message=None)
        frames = self._extract_frames(clip_path, config.VIDEO_ANALYSIS_SAMPLE_OFFSETS)
        if not frames:
            self._set_status(event_id, "failed", error_message="Không đọc được frame nào từ video evidence.")
            return

        health_url = config.COSMOS_VIDEO_URL.rsplit("/", 1)[0] + "/health"
        try:
            health = requests.get(health_url, timeout=5)
            health_data = health.json() if health.ok else {}
        except requests.RequestException as exc:
            self._set_status(event_id, "failed", error_message=f"Cosmos chưa sẵn sàng: {exc}")
            return
        if health_data.get("status") != "ready":
            self._set_status(event_id, "failed", error_message=f"Cosmos chưa sẵn sàng: {health_data.get('status', health.status_code)}")
            return

        self._set_status(event_id, "analyzing_frames")
        event_time = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
        results = []
        for offset, jpeg_bytes in frames:
            captured_at = (event_time - timedelta(seconds=config.PRE_BUFFER_SEC) + timedelta(seconds=offset)).astimezone()
            payload = self._analyze_frame(jpeg_bytes, event, captured_at)
            results.append({
                "offset_seconds": offset,
                "captured_at": captured_at.isoformat(timespec="seconds"),
                "inference_ms": payload.get("inference_ms"),
                "result": payload["result"],
            })

        aggregate = self._aggregate(results)
        self._set_status(
            event_id,
            "completed",
            summary=aggregate["summary"],
            risk_level=aggregate["risk_level"],
            events=aggregate["events"],
            frames=results,
            video_model=health_data.get("video_model"),
            analyzed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    @staticmethod
    def _extract_frames(clip_path: Path, offsets) -> list[tuple[float, bytes]]:
        capture = cv2.VideoCapture(str(clip_path))
        frames = []
        try:
            for raw_offset in offsets:
                offset = max(0.0, float(raw_offset))
                capture.set(cv2.CAP_PROP_POS_MSEC, offset * 1000)
                ok, frame = capture.read()
                if not ok:
                    continue
                encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
                if encoded:
                    frames.append((offset, buffer.tobytes()))
        finally:
            capture.release()
        return frames

    @staticmethod
    def _analyze_frame(jpeg_bytes: bytes, event: dict, captured_at: datetime) -> dict:
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Cosmos-Device-Id": str(config.NVR_HOST),
            "X-Cosmos-Channel": str(event["channel"]),
            "X-Cosmos-Captured-At": captured_at.isoformat(timespec="seconds"),
            "X-Cosmos-Analysis-Source": "event_clip",
        }
        response = None
        for attempt in range(3):
            response = requests.post(config.COSMOS_VIDEO_URL, data=jpeg_bytes, headers=headers, timeout=90)
            if response.status_code != 429:
                break
            time.sleep(attempt + 1)
        if response is None or not response.ok:
            code = response.status_code if response is not None else "unknown"
            raise RuntimeError(f"Cosmos video analysis failed: HTTP {code}")
        payload = response.json()
        if payload.get("status") != "ok" or not isinstance(payload.get("result"), dict):
            raise RuntimeError(payload.get("detail", "Cosmos trả kết quả video không hợp lệ."))
        return payload

    @staticmethod
    def _aggregate(frames: list[dict]) -> dict:
        risk_level = "none"
        summaries = []
        max_counts = {}
        for frame in frames:
            result = frame["result"]
            risk = str(result.get("risk_level", "none")).lower()
            if _RISK_ORDER.get(risk, 0) > _RISK_ORDER[risk_level]:
                risk_level = risk
            summary = " ".join(str(result.get("summary", "")).split())
            if summary and summary not in summaries:
                summaries.append(summary)
            for item in result.get("events", []):
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label", "")).strip()
                try:
                    count = max(0, int(item.get("count", 0)))
                except (TypeError, ValueError):
                    continue
                if label:
                    max_counts[label] = max(max_counts.get(label, 0), count)
        return {
            "summary": "\n".join(summaries),
            "risk_level": risk_level,
            "events": [{"label": label, "count": count} for label, count in sorted(max_counts.items())],
        }
