"""Background processing for audio attached to an NVR anomaly event."""

import hashlib
import os
import queue
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import requests

import config
import database
import video_clipper


class AudioAnalysisWorker:
    def __init__(self, on_updated: Optional[Callable[[int], None]] = None):
        self._on_updated = on_updated
        self._queue: queue.Queue[Optional[int]] = queue.Queue()
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="audio-analysis-worker")
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def enqueue(self, event_id: int) -> None:
        self._queue.put(event_id)

    def _run(self) -> None:
        while self._running.is_set():
            try:
                event_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if event_id is None:
                continue
            self._process(event_id)

    def _set_status(self, event_id: int, status: str, **values) -> None:
        database.update_audio_analysis(event_id, status=status, **values)
        if self._on_updated:
            self._on_updated(event_id)

    def _process(self, event_id: int) -> None:
        event = database.get_event_by_id(event_id)
        if not event:
            return

        try:
            event_time = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
            delay = config.POST_BUFFER_SEC - (datetime.now() - event_time).total_seconds()
            if delay > 0:
                self._set_status(event_id, "waiting_for_post_buffer")
                time.sleep(delay)

            self._set_status(event_id, "downloading_clip")
            clip_filename = f"clip_ch{event['channel']}_{event_time.strftime('%Y%m%d_%H%M%S')}.mp4"
            clip_filename = video_clipper.clip_event_video(
                channel=event["channel"],
                event_timestamp=event_time,
                output_filename=clip_filename,
                event_type=event["event_type"],
                event_code=event["event_code"],
            )
            if not clip_filename:
                self._set_status(event_id, "failed", error_message="Không thể tải clip thật từ NVR.")
                return
            database.update_event_clip(event_id, clip_filename)
            self._notify(event_id)

            clip_path = Path(config.CLIPS_DIR) / clip_filename
            self._set_status(event_id, "extracting_audio")
            if not self._has_audio_stream(clip_path):
                self._set_status(event_id, "no_audio", ignored_reason="no_audio_track")
                return

            wav_path = self._extract_wav(clip_path)
            try:
                self._transcribe(event_id, event, wav_path)
            finally:
                Path(wav_path).unlink(missing_ok=True)
        except Exception as exc:
            self._set_status(event_id, "failed", error_message=str(exc))

    def _has_audio_stream(self, clip_path: Path) -> bool:
        result = subprocess.run(
            [config.FFPROBE_PATH, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(clip_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or result.returncode}")
        return bool(result.stdout.strip())

    def _extract_wav(self, clip_path: Path) -> str:
        handle, wav_path = tempfile.mkstemp(prefix="camera_audio_", suffix=".wav")
        os.close(handle)
        result = subprocess.run(
            [config.FFMPEG_PATH, "-y", "-i", str(clip_path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        if result.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
            Path(wav_path).unlink(missing_ok=True)
            raise RuntimeError("Không thể tách WAV 16 kHz từ clip.")
        return wav_path

    def _transcribe(self, event_id: int, event: dict, wav_path: str) -> None:
        self._set_status(event_id, "transcribing")
        health_url = config.COSMOS_AUDIO_URL.rsplit("/", 1)[0] + "/health"
        try:
            health = requests.get(health_url, timeout=5)
            health_data = health.json() if health.ok else {}
        except requests.RequestException as exc:
            self._set_status(event_id, "failed", error_message=f"Cosmos chưa sẵn sàng: {exc}")
            return
        if health_data.get("status") != "ready":
            self._set_status(event_id, "failed", error_message=f"Cosmos chưa sẵn sàng: {health_data.get('status', health.status_code)}")
            return

        wav_bytes = Path(wav_path).read_bytes()
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Cosmos-Device-Id": config.NVR_HOST,
            "X-Cosmos-Channel": str(event["channel"]),
            "X-Cosmos-Captured-At": event["timestamp"],
            "X-Cosmos-Audio-Source": "event_clip",
            "X-Cosmos-Audio-Sha256": hashlib.sha256(wav_bytes).hexdigest(),
        }
        response = requests.post(config.COSMOS_AUDIO_URL, data=wav_bytes, headers=headers, timeout=90)
        if not response.ok:
            self._set_status(event_id, "failed", error_message=f"Cosmos transcription failed: HTTP {response.status_code}")
            return
        result = response.json()
        if result.get("status") != "ok":
            self._set_status(event_id, "failed", error_message=result.get("detail", "Cosmos transcription failed"))
            return
        self._set_status(
            event_id,
            "completed",
            transcript=result.get("text", ""),
            speech_detected=int(bool(result.get("speech_detected"))),
            audio_rms=result.get("audio_rms"),
            active_speech_seconds=result.get("active_speech_seconds"),
            ignored_reason=result.get("ignored_reason"),
            audio_model=result.get("audio_model"),
            analyzed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    def _notify(self, event_id: int) -> None:
        if self._on_updated:
            self._on_updated(event_id)
