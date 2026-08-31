# coding=utf-8
"""
Chuyển âm thanh / video thành văn bản (Speech-to-Text Studio).
Hỗ trợ kiểm thử trực tiếp cả file video (MP4, MKV, AVI, DAV...) lẫn audio (WAV, MP3, M4A...).
Chế độ hoạt động:
  1. Qua HTTP Live Service (/transcribe) - kiểm thử pipeline như khi xem camera trực tiếp.
  2. Chạy trực tiếp nội bộ (Local Whisper/PhoWhisper trên GPU/CPU) - không cần bật FastAPI server.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Preload torch on Windows before PyQt5 loads C++ runtime/DLLs to prevent WinError 1114 in c10.dll
try:
    import torch
except Exception:
    pass

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QSplitter, QStyle,
    QVBoxLayout, QWidget,
)


def _transcribe_url(url: str) -> str:
    """Accept either a Cosmos /analyze URL, base URL, or /transcribe URL."""
    value = url.rstrip("/")
    if value.endswith("/transcribe"):
        return value
    if value.endswith("/analyze"):
        return value.rsplit("/", 1)[0] + "/transcribe"
    return value + "/transcribe"


def _service_health_check(base_url: str) -> dict:
    """Check if the Live Service is running and return health info."""
    clean_base = base_url.rstrip("/")
    if clean_base.endswith(("/transcribe", "/analyze")):
        clean_base = clean_base.rsplit("/", 1)[0]
    health_url = clean_base + "/health"
    req = Request(health_url, headers={"User-Agent": "VideoToTextDemo/1.0"})
    with urlopen(req, timeout=1.5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _default_endpoint() -> str:
    """Prefer configured server or default to 8765 / 8770."""
    configured = os.getenv("COSMOS_LIVE_URL", "http://127.0.0.1:8765/analyze")
    endpoint = _transcribe_url(configured)
    base = endpoint.rsplit("/", 1)[0]
    try:
        health = _service_health_check(base)
        if health.get("status") in {"ready", "loading"}:
            return endpoint
    except Exception:
        pass

    for port in (8765, 8770):
        candidate_base = f"http://127.0.0.1:{port}"
        try:
            health = _service_health_check(candidate_base)
            if health.get("status") in {"ready", "loading"}:
                return f"{candidate_base}/transcribe"
        except Exception:
            pass

    return endpoint


def _format_offset(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    return str(timedelta(seconds=int(seconds))).zfill(8)


def _format_srt_time(seconds: float) -> str:
    """Format seconds into SRT timestamp 00:00:00,000."""
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class TranscribeWorker(QObject):
    progress = pyqtSignal(int, int)
    segment_received = pyqtSignal(dict)
    status = pyqtSignal(str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        media_path: str,
        mode: str,  # "service" or "local"
        endpoint: str,
        chunk_seconds: float,
        language: str,
        min_rms: float,
        beam_size: int,
        require_agreement: bool,
        local_model_id: str = "vinai/PhoWhisper-small",
    ):
        super().__init__()
        self.media_path = Path(media_path)
        self.mode = mode
        self.endpoint = endpoint
        self.chunk_seconds = chunk_seconds
        self.language = language if language != "auto" else None
        self.min_rms = min_rms
        self.beam_size = beam_size
        self.require_agreement = require_agreement
        self.local_model_id = local_model_id
        self.cancelled = threading.Event()
        self._local_pipeline = None

    def cancel(self):
        self.cancelled.set()

    @staticmethod
    def _ffmpeg_path() -> str:
        configured = os.getenv("COSMOS_AUDIO_FFMPEG", "").strip()
        if configured and Path(configured).is_file():
            return configured
        found = shutil.which("ffmpeg")
        if found:
            return found
        project_root = Path(__file__).resolve().parents[2]
        for candidate in (
            project_root / "ffmpeg" / "bin" / "ffmpeg.exe",
            project_root / "ffmpeg" / "ffmpeg.exe",
            Path("C:/ffmpeg/ffmpeg-8.0.1-essentials_build/bin/ffmpeg.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
        return "ffmpeg"

    def _extract_audio(self, wav_path: Path):
        """Extract or convert any audio/video container to 16kHz Mono PCM16 WAV with ultra-fast demuxing."""
        ffmpeg = self._ffmpeg_path()
        command = [
            ffmpeg, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-threads", "2", "-probesize", "32768", "-analyzeduration", "0",
            "-i", str(self.media_path), "-map", "0:a:0?",
            "-vn", "-sn", "-dn",
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path),
        ]
        completed = subprocess.run(command, capture_output=True, timeout=300, check=False)
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", "replace").strip()
            if "matches no streams" in detail or "Stream map" in detail:
                raise RuntimeError("File không chứa luồng âm thanh nào để nhận dạng.")
            raise RuntimeError("FFmpeg trích xuất âm thanh thất bại: " + (detail[-400:] or "Lỗi không xác định"))
        if not wav_path.exists() or wav_path.stat().st_size <= 44:
            raise RuntimeError("Không tìm thấy dữ liệu âm thanh hợp lệ trong file.")

    @staticmethod
    def _wav_bytes(params, frames: bytes) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as chunk:
            chunk.setparams(params)
            chunk.writeframes(frames)
        return output.getvalue()

    def _post_chunk_to_service(self, wav_body: bytes, sequence: int, captured_at: str) -> dict:
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Cosmos-Device-Id": "video-to-text-demo",
            "X-Cosmos-Channel": "0",
            "X-Cosmos-Captured-At": captured_at,
            "X-Cosmos-Audio-Source": "file",
            "X-Cosmos-Audio-Sha256": hashlib.sha256(wav_body).hexdigest(),
        }
        request = Request(self.endpoint, data=wav_body, method="POST", headers=headers)
        try:
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"Service trả về HTTP {exc.code}: {detail[:200]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Không kết nối được Live Service: {exc.reason}") from exc

    def _transcribe_locally(self, wav_body: bytes) -> dict:
        """Run speech-to-text directly in this process via transformers."""
        import numpy as np

        marker = wav_body.find(b"data")
        offset = marker + 8 if marker >= 0 else 44
        pcm = wav_body[offset:]
        if len(pcm) % 2:
            pcm = pcm[:-1]
        # Khử DC Offset và chuẩn hóa âm lượng (Peak Normalization)
        samples = samples - np.mean(samples)
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        if peak > 1e-4:
            normalized_samples = (samples / peak * 0.90).astype(np.float32)
        else:
            normalized_samples = samples

        rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0

        frame_size = 480  # 30 ms tại 16kHz
        frame_count = samples.size // frame_size
        if rms < self.min_rms or frame_count < 4:
            has_speech = False
        else:
            frames = samples[:frame_count * frame_size].reshape(frame_count, frame_size)
            frame_rms = np.sqrt(np.mean(np.square(frames), axis=1))
            noise_floor = max(float(np.percentile(frame_rms, 20)), 1e-6)
            active_threshold = max(self.min_rms, noise_floor * 1.8)
            active_seconds = float(np.count_nonzero(frame_rms >= active_threshold) * 0.03)
            dynamic_ratio = float(np.percentile(frame_rms, 90) / noise_floor)
            has_speech = active_seconds >= 0.30 and dynamic_ratio >= 1.40

        if not has_speech:
            return {
                "text": "",
                "speech_detected": False,
                "ignored_reason": "no_speech_activity",
                "audio_rms": round(rms, 6),
                "transcription_ms": 0,
            }

        if self._local_pipeline is None:
            self.status.emit(f"Đang tải mô hình {self.local_model_id}...")
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

            use_cuda = torch.cuda.is_available()
            if not use_cuda:
                torch.set_num_threads(min(2, os.cpu_count() or 2))
            dtype = torch.float16 if use_cuda else torch.float32
            if use_cuda:
                torch.backends.cudnn.benchmark = True
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.local_model_id,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
                use_safetensors=False,
            )
            if use_cuda:
                model.to("cuda")
            model.eval()
            processor = AutoProcessor.from_pretrained(self.local_model_id)
            self._local_pipeline = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                dtype=dtype,
                device=0 if use_cuda else -1,
                max_new_tokens=128,
            )
            # Warmup model
            try:
                with torch.inference_mode():
                    dummy = np.zeros(16000, dtype=np.float32)
                    self._local_pipeline(dummy, generate_kwargs={"task": "transcribe", "num_beams": 1, "max_new_tokens": 8})
            except Exception:
                pass

        t0 = time.perf_counter()
        try:
            import torch
            gen_kwargs = {
                "task": "transcribe",
                "do_sample": False,
                "num_beams": self.beam_size,
                "condition_on_prev_tokens": False,
                "temperature": 0.0,
                "repetition_penalty": 1.30,
                "no_repeat_ngram_size": 3,
            }
            if self.language:
                gen_kwargs["language"] = self.language

            with torch.inference_mode():
                res = self._local_pipeline(normalized_samples, generate_kwargs=gen_kwargs)
            text = " ".join(str(res.get("text", "")).split())

            # Bộ lọc chống ảo giác (Hallucination filter) triệt để
            if text:
                text_clean = text.strip()
                text_lower = text_clean.lower()
                hallucinations = [
                    "cảm ơn các bạn đã xem", "cảm ơn các bạn đã theo dõi", "cảm ơn đã xem",
                    "hãy like và subscribe", "đăng ký kênh", "hãy đăng ký", "subscribe",
                    "hẹn gặp lại", "chúc các bạn", "nhà hàng đầu có thể", "nàng thông cáo", "nàng hơi",
                    "lalaschool", "thanks for watching", "subtitles by"
                ]
                if any(h in text_lower for h in hallucinations) or len(text_clean) < 2:
                    text = ""
                else:
                    import re
                    tokens = re.findall(r"\w+", text_lower, flags=re.UNICODE)
                    if len(tokens) >= 5:
                        if len(set(tokens)) / len(tokens) < 0.40:
                            text = ""
                        else:
                            for period in range(1, min(6, len(tokens) // 2 + 1)):
                                matches = sum(tokens[idx] == tokens[idx - period] for idx in range(period, len(tokens)))
                                if matches / (len(tokens) - period) >= 0.60:
                                    text = ""
                                    break
            latency = int((time.perf_counter() - t0) * 1000)

            ignored_reason = None
            if self.require_agreement and text:
                v_kwargs = dict(gen_kwargs)
                v_kwargs["num_beams"] = 1
                with torch.inference_mode():
                    v_res = self._local_pipeline(tmp_path, generate_kwargs=v_kwargs)
                v_text = " ".join(str(v_res.get("text", "")).split())
                import difflib
                sim = difflib.SequenceMatcher(None, text.casefold(), v_text.casefold()).ratio()
                if sim < 0.70:
                    ignored_reason = "decoder_disagreement"
                    text = ""

            return {
                "text": text,
                "speech_detected": bool(text),
                "ignored_reason": ignored_reason,
                "audio_rms": round(rms, 6),
                "transcription_ms": latency,
            }
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def run(self):
        try:
            with tempfile.TemporaryDirectory(prefix="cosmos_transcribe_") as temp_dir:
                wav_path = Path(temp_dir) / "converted_audio.wav"
                self.status.emit("Đang trích xuất / chuyển đổi âm thanh sang 16kHz PCM16...")
                self._extract_audio(wav_path)

                with wave.open(str(wav_path), "rb") as source:
                    framerate = source.getframerate()
                    frames_per_chunk = max(1, round(self.chunk_seconds * framerate))
                    total_frames = source.getnframes()
                    total_chunks = max(1, (total_frames + frames_per_chunk - 1) // frames_per_chunk)
                    params = source.getparams()

                    for seq in range(total_chunks):
                        if self.cancelled.is_set():
                            self.completed.emit("Đã dừng theo yêu cầu của người dùng.")
                            return

                        raw_frames = source.readframes(frames_per_chunk)
                        if not raw_frames:
                            break

                        start_sec = seq * self.chunk_seconds
                        end_sec = min(start_sec + self.chunk_seconds, total_frames / framerate)
                        self.status.emit(
                            f"Đang phân tích đoạn {seq + 1} / {total_chunks} ({_format_offset(start_sec)} ➔ {_format_offset(end_sec)})..."
                        )

                        chunk_wav = self._wav_bytes(params, raw_frames)
                        captured_at = time.strftime("%Y-%m-%dT%H:%M:%S")

                        if self.mode == "service":
                            result = self._post_chunk_to_service(chunk_wav, seq, captured_at)
                        else:
                            result = self._transcribe_locally(chunk_wav)

                        segment_info = {
                            "seq": seq + 1,
                            "start": start_sec,
                            "end": end_sec,
                            "text": str(result.get("text", "")).strip(),
                            "rms": result.get("audio_rms", 0.0),
                            "latency_ms": result.get("transcription_ms", 0),
                            "ignored": result.get("ignored_reason"),
                            "speech_detected": result.get("speech_detected", False),
                            "sha": hashlib.sha256(chunk_wav).hexdigest()[:12],
                        }
                        self.segment_received.emit(segment_info)
                        self.progress.emit(seq + 1, total_chunks)

            self.completed.emit("Hoàn tất chuyển âm thanh thành văn bản.")
        except Exception as exc:
            self.failed.emit(str(exc))


class VideoToTextWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chuyển âm video/audio thành văn bản — Speech-to-Text Studio")
        self.resize(960, 720)
        self.setMinimumSize(840, 580)
        self._thread = None
        self._worker = None
        self._segments = []
        self._build_ui()

    def _build_ui(self):
        root = QWidget(self)
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Info Banner
        header = QLabel(
            "<b>🎧 STUDIO PHÂN TÍCH TIẾNG NÓI & CHUYỂN THÀNH VĂN BẢN (SPEECH-TO-TEXT)</b><br>"
            "<span style='color: #64748B;'>Hỗ trợ file Video (MP4, MKV, AVI, DAV...) và Audio (WAV, MP3, M4A, AAC, FLAC...). "
            "Sử dụng mô hình tiếng Việt chuyên dụng <b>vinai/PhoWhisper</b> kết hợp lọc nhiễu VAD và xác thực 2 lớp chống bịa lời.</span>"
        )
        header.setWordWrap(True)
        main_layout.addWidget(header)

        splitter = QSplitter(Qt.Vertical, root)

        # Config Panel
        config_box = QGroupBox("Cấu hình & Nguồn dữ liệu", splitter)
        config_layout = QVBoxLayout(config_box)
        config_layout.setSpacing(10)

        # File selection
        file_row = QHBoxLayout()
        self.file_input = QLineEdit(config_box)
        self.file_input.setPlaceholderText("Chọn file video (.mp4, .mkv, .dav...) hoặc audio (.wav, .mp3, .m4a)...")
        browse_btn = QPushButton("📁 Chọn file...", config_box)
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.file_input, 1)
        file_row.addWidget(browse_btn)
        config_layout.addLayout(file_row)

        # Mode & Endpoint row
        mode_form = QFormLayout()
        mode_form.setSpacing(8)

        mode_row = QHBoxLayout()
        self.mode_combo = QComboBox(config_box)
        self.mode_combo.addItem("🌐 Qua Live Service (/transcribe HTTP)", "service")
        self.mode_combo.addItem("💻 Trực tiếp nội bộ (Local GPU/CPU Whisper)", "local")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.test_conn_btn = QPushButton("Kiểm tra kết nối", config_box)
        self.test_conn_btn.clicked.connect(self._test_service_connection)

        mode_row.addWidget(self.mode_combo, 1)
        mode_row.addWidget(self.test_conn_btn)
        mode_form.addRow("Chế độ xử lý:", mode_row)

        self.endpoint_input = QLineEdit(_default_endpoint(), config_box)
        mode_form.addRow("Địa chỉ Service:", self.endpoint_input)

        # Local model selection (only active in local mode)
        self.model_combo = QComboBox(config_box)
        self.model_combo.addItem("vinai/PhoWhisper-small (Khuyến nghị tiếng Việt)", "vinai/PhoWhisper-small")
        self.model_combo.addItem("vinai/PhoWhisper-medium (Chất lượng cao nhất)", "vinai/PhoWhisper-medium")
        self.model_combo.addItem("openai/whisper-base (Đa ngôn ngữ nhẹ)", "openai/whisper-base")
        self.model_combo.addItem("openai/whisper-small (Đa ngôn ngữ vừa)", "openai/whisper-small")
        self.model_combo.setEnabled(False)
        mode_form.addRow("Mô hình Local:", self.model_combo)

        # Parameters row
        params_row = QHBoxLayout()

        self.chunk_spin = QDoubleSpinBox(config_box)
        self.chunk_spin.setRange(2.0, 60.0)
        self.chunk_spin.setValue(10.0)
        self.chunk_spin.setSuffix(" giây")
        params_row.addWidget(QLabel("Đoạn cắt:"))
        params_row.addWidget(self.chunk_spin)
        params_row.addSpacing(12)

        self.lang_combo = QComboBox(config_box)
        self.lang_combo.addItem("Tiếng Việt (vi)", "vi")
        self.lang_combo.addItem("Tự động nhận diện (auto)", "auto")
        self.lang_combo.addItem("Tiếng Anh (en)", "en")
        params_row.addWidget(QLabel("Ngôn ngữ:"))
        params_row.addWidget(self.lang_combo)
        params_row.addSpacing(12)

        self.rms_spin = QDoubleSpinBox(config_box)
        self.rms_spin.setRange(0.001, 0.100)
        self.rms_spin.setSingleStep(0.002)
        self.rms_spin.setDecimals(3)
        self.rms_spin.setValue(0.008)
        self.rms_spin.setToolTip("Ngưỡng năng lượng âm thanh tối thiểu. Mức 0.008 giúp loại bỏ tiếng xì/nhiễu gió phòng, chống AI tự bịa câu.")
        params_row.addWidget(QLabel("Lọc nhiễu RMS:"))
        params_row.addWidget(self.rms_spin)
        params_row.addSpacing(12)

        self.beam_spin = QSpinBox(config_box)
        self.beam_spin.setRange(1, 10)
        self.beam_spin.setValue(5)
        params_row.addWidget(QLabel("Beam search:"))
        params_row.addWidget(self.beam_spin)
        params_row.addStretch(1)

        mode_form.addRow("Tham số tinh chỉnh:", params_row)

        self.agreement_check = QCheckBox(
            "Xác thực 2 lớp giải mã (Decoder Agreement — chặn câu model tự bịa khi âm thanh mờ/nhiễu)", config_box
        )
        self.agreement_check.setChecked(False)
        mode_form.addRow("", self.agreement_check)

        config_layout.addLayout(mode_form)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ Bắt đầu phân tích âm thanh", config_box)
        self.start_btn.setStyleSheet("font-weight: 700; padding: 6px 16px; background-color: #2563EB; color: white;")
        self.start_btn.clicked.connect(self._start)

        self.stop_btn = QPushButton("⏹ Dừng", config_box)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)

        self.clear_btn = QPushButton("Dọn kết quả", config_box)
        self.clear_btn.clicked.connect(self._clear_results)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch(1)
        config_layout.addLayout(btn_layout)

        # Result Panel
        result_box = QGroupBox("Kết quả nhận dạng & Bóc băng", splitter)
        result_layout = QVBoxLayout(result_box)
        result_layout.setSpacing(8)

        self.progress_bar = QProgressBar(result_box)
        self.progress_bar.setTextVisible(True)
        result_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Sẵn sàng kiểm thử.")
        self.status_label.setStyleSheet("color: #475569; font-weight: 600;")
        result_layout.addWidget(self.status_label)

        self.output_edit = QPlainTextEdit(result_box)
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Dòng thời gian transcript và dữ liệu phân tích sẽ hiển thị tại đây...")
        result_layout.addWidget(self.output_edit, 1)

        # Export & Tool buttons
        export_layout = QHBoxLayout()
        self.copy_btn = QPushButton("📋 Sao chép văn bản", result_box)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)

        self.save_txt_btn = QPushButton("💾 Lưu file TXT", result_box)
        self.save_txt_btn.clicked.connect(self._save_txt)

        self.save_srt_btn = QPushButton("🎬 Xuất phụ đề SRT", result_box)
        self.save_srt_btn.clicked.connect(self._save_srt)

        export_layout.addWidget(self.copy_btn)
        export_layout.addWidget(self.save_txt_btn)
        export_layout.addWidget(self.save_srt_btn)
        export_layout.addStretch(1)
        result_layout.addLayout(export_layout)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

    def _on_mode_changed(self, index: int):
        is_local = self.mode_combo.currentData() == "local"
        self.endpoint_input.setEnabled(not is_local)
        self.test_conn_btn.setEnabled(not is_local)
        self.model_combo.setEnabled(is_local)

    def _test_service_connection(self):
        endpoint = self.endpoint_input.text().strip()
        try:
            health = _service_health_check(endpoint)
            status = health.get("status", "unknown")
            model = health.get("audio_model", "Chưa rõ")
            profile = health.get("live_prompt_profile", "")
            QMessageBox.information(
                self,
                "Kết nối Live Service",
                f"✅ Dịch vụ đang hoạt động tốt!\n"
                f"- Trạng thái: {status}\n"
                f"- Mô hình tiếng nói: {model}\n"
                f"- Profile: {profile or 'mặc định'}",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Lỗi kết nối",
                f"❌ Không thể kết nối tới Service tại {endpoint}\n\nChi tiết: {exc}\n\n"
                f"Mẹo: Bạn có thể chọn chế độ 'Trực tiếp nội bộ (Local Whisper)' để chạy không cần bật server!",
            )

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file Video hoặc Audio để phân tích",
            self.file_input.text() or str(Path.home()),
            "Media Files (*.mp4 *.mkv *.avi *.mov *.dav *.wmv *.wav *.mp3 *.m4a *.aac *.flac *.ogg);;Video (*.mp4 *.mkv *.avi *.dav);;Audio (*.wav *.mp3 *.m4a *.flac);;All Files (*)",
        )
        if path:
            self.file_input.setText(path)

    def _clear_results(self):
        self.output_edit.clear()
        self._segments.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Đã xóa dữ liệu hiển thị.")

    def _start(self):
        media_path = self.file_input.text().strip()
        if not Path(media_path).is_file():
            QMessageBox.warning(self, "Chưa chọn file", "Vui lòng chọn một file video hoặc audio hợp lệ trên máy.")
            return

        mode = self.mode_combo.currentData()
        endpoint = _transcribe_url(self.endpoint_input.text().strip())

        if mode == "service" and not endpoint.startswith(("http://", "https://")):
            QMessageBox.warning(self, "URL không hợp lệ", "Địa chỉ Live Service phải bắt đầu bằng http:// hoặc https://")
            return

        self._clear_results()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self._thread = QThread(self)
        self._worker = TranscribeWorker(
            media_path=media_path,
            mode=mode,
            endpoint=endpoint,
            chunk_seconds=self.chunk_spin.value(),
            language=self.lang_combo.currentData(),
            min_rms=self.rms_spin.value(),
            beam_size=self.beam_spin.value(),
            require_agreement=self.agreement_check.isChecked(),
            local_model_id=self.model_combo.currentData(),
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.segment_received.connect(self._on_segment_received)
        self._worker.status.connect(self.status_label.setText)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _stop(self):
        if self._worker:
            self._worker.cancel()
            self.stop_btn.setEnabled(False)
            self.status_label.setText("Đang dừng sau khi hoàn tất đoạn hiện tại...")

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_segment_received(self, seg: dict):
        self._segments.append(seg)
        start_str = _format_offset(seg["start"])
        end_str = _format_offset(seg["end"])
        text = seg["text"]

        # Chỉ xuất ra màn hình khi có lời nói thực tế
        if text:
            line = f"[{start_str} ➔ {end_str}] {text}\n"
            self.output_edit.appendPlainText(line)

    def _on_completed(self, message: str):
        self.status_label.setText(f"✅ {message}")
        valid_texts = [s["text"] for s in self._segments if s.get("text")]
        if valid_texts:
            summary = f"\n--- TỔNG KẾT: Đã nhận dạng {len(valid_texts)} đoạn có lời nói ---"
            self.output_edit.appendPlainText(summary)
        self._dispose_worker()

    def _on_failed(self, message: str):
        self.status_label.setText(f"❌ Lỗi: {message}")
        QMessageBox.warning(self, "Lỗi phân tích âm thanh", message)
        self._dispose_worker()

    def _dispose_worker(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self._thread:
            self._thread.quit()
            self._thread.wait(1000)
            self._thread.deleteLater()
        if self._worker:
            self._worker.deleteLater()
        self._thread = None
        self._worker = None

    def _copy_to_clipboard(self):
        text = self.output_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Thông báo", "Chưa có kết quả để sao chép.")
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Thành công", "Đã sao chép toàn bộ transcript vào Clipboard!")

    def _save_txt(self):
        if not self._segments:
            QMessageBox.information(self, "Thông báo", "Chưa có kết quả để lưu.")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Lưu file transcript TXT", "transcript.txt", "Text Files (*.txt)")
        if not save_path:
            return
        lines = []
        for s in self._segments:
            if s.get("text"):
                lines.append(f"[{_format_offset(s['start'])} - {_format_offset(s['end'])}] {s['text']}")
        Path(save_path).write_text("\n".join(lines), encoding="utf-8")
        QMessageBox.information(self, "Thành công", f"Đã lưu kết quả vào:\n{save_path}")

    def _save_srt(self):
        valid_segments = [s for s in self._segments if s.get("text")]
        if not valid_segments:
            QMessageBox.information(self, "Thông báo", "Không có đoạn có lời nói nào để tạo phụ đề SRT.")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Xuất phụ đề SRT", "subtitles.srt", "SubRip Subtitle (*.srt)")
        if not save_path:
            return
        srt_lines = []
        for index, s in enumerate(valid_segments, 1):
            srt_lines.append(str(index))
            srt_lines.append(f"{_format_srt_time(s['start'])} --> {_format_srt_time(s['end'])}")
            srt_lines.append(s["text"])
            srt_lines.append("")
        Path(save_path).write_text("\n".join(srt_lines), encoding="utf-8")
        QMessageBox.information(self, "Thành công", f"Đã xuất phụ đề SRT thành công:\n{save_path}")

    def closeEvent(self, event):
        if self._worker:
            self._worker.cancel()
        event.accept()


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = VideoToTextWindow()
    window.show()
    sys.exit(app.exec_())
