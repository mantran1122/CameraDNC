import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gemini_video_report  # noqa: E402


class GeminiVideoReportTest(unittest.TestCase):
    def test_disabled_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            report, model = gemini_video_report.generate_final_video_report({}, [], None)
        self.assertIsNone(report)
        self.assertIsNone(model)

    def test_uses_only_structured_evidence(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"summary":"Cần kiểm tra clip gốc.","risk_level":"medium","recommended_action":"Thông báo bảo vệ.","evidence":[{"source":"Cosmos","detail":"[0-10s] có giằng co"}]}' }]}}]
        }
        windows = [{"window_start_seconds": 0, "window_end_seconds": 10, "result": {"summary": "Có giằng co", "risk_level": "medium", "events": []}}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "CAMERAAI_GEMINI_MODEL": "test-model"}, clear=True), \
             patch.object(gemini_video_report.requests, "post", return_value=response) as post:
            report, model = gemini_video_report.generate_final_video_report({"event_code": "Fight", "channel": 1}, windows, {"status": "completed", "transcript": "Dừng lại"})
        self.assertEqual(model, "test-model")
        self.assertEqual(report["risk_level"], "medium")
        request_payload = post.call_args.kwargs["json"]
        self.assertIn("visual_windows_from_cosmos", request_payload["contents"][0]["parts"][0]["text"])
        self.assertNotIn("clip_filename", request_payload["contents"][0]["parts"][0]["text"])


if __name__ == "__main__":
    unittest.main()
