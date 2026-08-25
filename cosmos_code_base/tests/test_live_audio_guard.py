import struct
import unittest

from live_service import _is_repetitive_transcript, _pcm16_wav_rms


class LiveAudioGuardTests(unittest.TestCase):
    def test_silence_has_zero_energy(self):
        wav = b"RIFF" + (b"\x00" * 36) + b"data" + struct.pack("<I", 400) + (b"\x00" * 400)
        self.assertEqual(_pcm16_wav_rms(wav), 0.0)

    def test_repetitive_whisper_loop_is_rejected(self):
        text = "Cảm ơn các bạn. " * 12
        self.assertTrue(_is_repetitive_transcript(text))

    def test_normal_vietnamese_sentence_is_kept(self):
        text = "Sinh viên vui lòng nộp hồ sơ tại bàn số hai trước khi nhận giấy xác nhận."
        self.assertFalse(_is_repetitive_transcript(text))


if __name__ == "__main__":
    unittest.main()
