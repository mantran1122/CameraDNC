import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audio_analysis_worker  # noqa: E402
import config  # noqa: E402
import database  # noqa: E402


class AudioAnalysisWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.original_post_buffer = config.POST_BUFFER_SEC
        database.DB_PATH = Path(self.temp_dir.name) / "camera_metadata.db"
        config.POST_BUFFER_SEC = 0
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        config.POST_BUFFER_SEC = self.original_post_buffer
        self.temp_dir.cleanup()

    def test_clip_without_audio_is_recorded_as_no_audio(self):
        event_id = database.save_event(
            event_code="SoundDetection",
            event_type="audio_anomaly",
            channel=1,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            description="Sound detected",
        )
        database.create_audio_analysis(event_id)
        worker = audio_analysis_worker.AudioAnalysisWorker()

        with patch.object(audio_analysis_worker.video_clipper, "clip_event_video", return_value="event.mp4"):
            with patch.object(worker, "_has_audio_stream", return_value=False):
                worker._process(event_id)

        analysis = database.get_audio_analysis(event_id)
        event = database.get_event_by_id(event_id)
        self.assertEqual(analysis["status"], "no_audio")
        self.assertEqual(analysis["ignored_reason"], "no_audio_track")
        self.assertEqual(event["clip_filename"], "event.mp4")

    def test_suggestion_is_grounded_and_validated(self):
        worker = audio_analysis_worker.AudioAnalysisWorker()
        old_url = config.AUDIO_SUGGESTION_API_URL
        old_key = config.AUDIO_SUGGESTION_API_KEY
        old_model = config.AUDIO_SUGGESTION_MODEL
        config.AUDIO_SUGGESTION_API_URL = "http://llm.test/v1/chat/completions"
        config.AUDIO_SUGGESTION_API_KEY = "test-key"
        config.AUDIO_SUGGESTION_MODEL = "test-model"
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": '{"summary":"Có tiếng nói ngắn.","risk_level":"low","recommended_action":"Kiểm tra clip.","evidence":[{"source":"audio transcript","detail":"Xin chào"}]}'}}]
        }
        try:
            with patch.object(audio_analysis_worker.requests, "post", return_value=response) as post:
                suggestion, error = worker._create_suggestion(
                    {"event_code": "SoundDetection", "description": "Sound", "metadata": {"Code": "SoundDetection"}},
                    {"transcript": "Xin chào", "speech_detected": 1, "ignored_reason": None},
                )
        finally:
            config.AUDIO_SUGGESTION_API_URL = old_url
            config.AUDIO_SUGGESTION_API_KEY = old_key
            config.AUDIO_SUGGESTION_MODEL = old_model

        self.assertIsNone(error)
        self.assertEqual(suggestion["risk_level"], "low")
        self.assertEqual(suggestion["evidence"][0]["source"], "audio transcript")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
