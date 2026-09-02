import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dahua_client  # noqa: E402


class DahuaEventParserTest(unittest.TestCase):
    def test_parses_semicolon_separated_event_record(self):
        listener = dahua_client.DahuaNVRListener()
        with patch.object(dahua_client.config, "ACTIVE_CHANNELS", [5]), \
             patch.object(dahua_client.database, "save_event", return_value=42) as save_event, \
             patch.object(dahua_client.database, "get_event_by_id", return_value=None):
            listener.process_event_block("Code=HumanTrait;action=Start;index=4")

        self.assertEqual(save_event.call_count, 1)
        self.assertEqual(save_event.call_args.kwargs["event_code"], "HumanTrait")
        self.assertEqual(save_event.call_args.kwargs["channel"], 5)
        self.assertEqual(save_event.call_args.kwargs["metadata_dict"]["action"], "Start")

    def test_selected_metadata_behavior_is_saved_as_anomaly_with_a_clip(self):
        listener = dahua_client.DahuaNVRListener()
        with patch.object(dahua_client.config, "ACTIVE_CHANNELS", [1]), \
             patch.object(dahua_client.config, "ABNORMAL_EVENT_CODES", ["HumanTrait"]), \
             patch.object(dahua_client.database, "save_event", return_value=42) as save_event, \
             patch.object(dahua_client.database, "get_event_by_id", return_value=None), \
             patch.object(dahua_client.video_clipper, "clip_event_video", return_value="clip.mp4") as clip_event_video:
            listener.process_event_block("Code=HumanTrait;action=Start;index=0")

        self.assertEqual(save_event.call_args.kwargs["event_type"], "video_anomaly")
        self.assertEqual(save_event.call_args.kwargs["clip_filename"], "clip.mp4")
        clip_event_video.assert_called_once()
