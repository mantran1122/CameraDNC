from pathlib import Path

from app.streamlit_app import PLAYBACK_INBOX, _analysis_args
from src.video_utils import _build_ffmpeg_chunk_command


def _flag_value(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


def test_playback_uses_fast_analysis_defaults(monkeypatch) -> None:
    for name in (
        "COSMOS_PLAYBACK_CHUNK_SECONDS",
        "COSMOS_PLAYBACK_SAMPLE_FPS",
        "COSMOS_PLAYBACK_MAX_NEW_TOKENS",
        "COSMOS_PLAYBACK_CHUNK_ENCODER",
    ):
        monkeypatch.delenv(name, raising=False)

    args = _analysis_args(PLAYBACK_INBOX / "recording.mp4", run_in_wsl=False)

    assert _flag_value(args, "--chunk-seconds") == "30"
    assert _flag_value(args, "--sample-fps") == "0.2"
    assert _flag_value(args, "--max-new-tokens") == "384"
    assert _flag_value(args, "--chunk-encoder") == "copy"


def test_regular_upload_does_not_force_playback_tuning(monkeypatch, tmp_path: Path) -> None:
    for name in (
        "COSMOS_CHUNK_SECONDS",
        "COSMOS_SAMPLE_FPS",
        "COSMOS_MAX_NEW_TOKENS",
        "COSMOS_CHUNK_ENCODER",
    ):
        monkeypatch.delenv(name, raising=False)

    args = _analysis_args(tmp_path / "upload.mp4", run_in_wsl=False)

    assert "--chunk-seconds" not in args
    assert "--sample-fps" not in args
    assert "--max-new-tokens" not in args
    assert "--chunk-encoder" not in args


def test_copy_encoder_does_not_reencode_video(tmp_path: Path) -> None:
    command = _build_ffmpeg_chunk_command(
        ffmpeg="ffmpeg",
        video_path=tmp_path / "source.mp4",
        chunk_path=tmp_path / "chunk.mp4",
        start_seconds=30,
        duration_seconds=30,
        encoder="copy",
    )

    assert command[command.index("-c:v") + 1] == "copy"
    assert "h264_nvenc" not in command
    assert "libx264" not in command
