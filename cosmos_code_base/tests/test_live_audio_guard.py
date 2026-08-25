import struct
import unittest

import numpy as np

from live_service import (
    _has_speech_activity,
    _is_duplicate_audio_transcript,
    _is_known_audio_hallucination,
    _is_repetitive_transcript,
    _last_audio_transcriptions,
    _pcm16_wav_rms,
)


class LiveAudioGuardTests(unittest.TestCase):
    def setUp(self):
        _last_audio_transcriptions.clear()

    @staticmethod
    def _wav(samples):
        pcm = np.asarray(samples, dtype="<i2").tobytes()
        return b"RIFF" + (b"\x00" * 36) + b"data" + struct.pack("<I", len(pcm)) + pcm

    def test_silence_has_zero_energy(self):
        wav = b"RIFF" + (b"\x00" * 36) + b"data" + struct.pack("<I", 400) + (b"\x00" * 400)
        self.assertEqual(_pcm16_wav_rms(wav), 0.0)

    def test_repetitive_whisper_loop_is_rejected(self):
        text = "Cảm ơn các bạn. " * 12
        self.assertTrue(_is_repetitive_transcript(text))

    def test_normal_vietnamese_sentence_is_kept(self):
        text = "Sinh viên vui lòng nộp hồ sơ tại bàn số hai trước khi nhận giấy xác nhận."
        self.assertFalse(_is_repetitive_transcript(text))

    def test_stationary_noise_is_not_speech(self):
        wav = self._wav(np.full(16000, 300, dtype=np.int16))
        detected, _, _ = _has_speech_activity(wav, 0.003)
        self.assertFalse(detected)

    def test_varying_voice_like_energy_is_speech(self):
        samples = np.zeros(16000, dtype=np.int16)
        samples[2400:7200] = (np.sin(np.arange(4800) / 5) * 5000).astype(np.int16)
        detected, _, active_seconds = _has_speech_activity(self._wav(samples), 0.003)
        self.assertTrue(detected)
        self.assertGreater(active_seconds, 0.2)

    def test_known_subscription_hallucination_is_rejected(self):
        self.assertTrue(_is_known_audio_hallucination(
            "Hãy subscribe cho kênh lalaschool để không bỏ lỡ những video hấp dẫn"
        ))

    def test_duplicate_across_chunks_is_rejected(self):
        text = "Mời sinh viên đến bàn số hai nhận hồ sơ."
        self.assertFalse(_is_duplicate_audio_transcript(text, "camera-1", "10", now=10))
        self.assertTrue(_is_duplicate_audio_transcript(text, "camera-1", "10", now=20))


if __name__ == "__main__":
    unittest.main()
