import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

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

