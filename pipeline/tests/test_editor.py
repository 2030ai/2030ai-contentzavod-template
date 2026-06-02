"""Tests for the video editor engine (all ffmpeg calls mocked)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.pipeline.editor import (
    EditConfig,
    VideoSegment,
    FreezeSegment,
    _get_duration,
    _tts_cache_key,
    _tts_cache_valid,
    _generate_tts,
    _add_branding,
    _apply_watermark,
    build,
)


def _close_coro(coro):
    """Close coroutine passed to mocked asyncio.run."""
    coro.close()


# --- _tts_cache_valid ---


def test_cache_valid_when_text_matches(tmp_path: Path):
    audio = tmp_path / "seg.mp3"
    marker = tmp_path / "seg.txt"
    audio.write_bytes(b"\xff" * 100)
    marker.write_text(_tts_cache_key("hello world", "elevenlabs", "voice1"), encoding="utf-8")
    assert _tts_cache_valid("hello world", audio, "elevenlabs", "voice1") is True


def test_cache_invalid_when_text_differs(tmp_path: Path):
    audio = tmp_path / "seg.mp3"
    marker = tmp_path / "seg.txt"
    audio.write_bytes(b"\xff" * 100)
    marker.write_text(_tts_cache_key("old text", "elevenlabs", None), encoding="utf-8")
    assert _tts_cache_valid("new text", audio, "elevenlabs", None) is False


def test_cache_invalid_when_engine_differs(tmp_path: Path):
    audio = tmp_path / "seg.mp3"
    marker = tmp_path / "seg.txt"
    audio.write_bytes(b"\xff" * 100)
    marker.write_text(_tts_cache_key("hello", "yandex", None), encoding="utf-8")
    assert _tts_cache_valid("hello", audio, "elevenlabs", "voice1") is False


def test_cache_invalid_legacy_marker(tmp_path: Path):
    """Legacy markers (text-only, no engine info) should be treated as invalid."""
    audio = tmp_path / "seg.mp3"
    marker = tmp_path / "seg.txt"
    audio.write_bytes(b"\xff" * 100)
    marker.write_text("hello world", encoding="utf-8")
    assert _tts_cache_valid("hello world", audio, "elevenlabs", "voice1") is False


def test_cache_invalid_when_no_audio(tmp_path: Path):
    assert _tts_cache_valid("text", tmp_path / "missing.mp3") is False


def test_cache_invalid_when_no_marker(tmp_path: Path):
    audio = tmp_path / "seg.mp3"
    audio.write_bytes(b"\xff" * 100)
    assert _tts_cache_valid("text", audio) is False


# --- _generate_tts ---


@patch("pipeline.pipeline.editor.generate_voice")
def test_generate_tts_skips_when_cached(mock_voice, tmp_path: Path):
    audio = tmp_path / "seg.mp3"
    marker = tmp_path / "seg.txt"
    audio.write_bytes(b"\xff" * 100)
    marker.write_text(_tts_cache_key("cached text", "yandex", None), encoding="utf-8")

    _generate_tts("cached text", audio, engine="yandex", voice_id=None)
    mock_voice.assert_not_called()


@patch("pipeline.pipeline.editor.verify_tts", return_value=(True, 0.9, "new text"))
@patch("pipeline.pipeline.editor.asyncio.run")
def test_generate_tts_calls_api_when_not_cached(mock_run, mock_verify, tmp_path: Path):
    audio = tmp_path / "seg.mp3"
    mock_run.side_effect = _close_coro

    _generate_tts("new text", audio, engine="elevenlabs", voice_id="v1")

    mock_run.assert_called_once()
    marker = tmp_path / "seg.txt"
    assert marker.read_text(encoding="utf-8") == _tts_cache_key("new text", "elevenlabs", "v1")


@patch("pipeline.pipeline.editor.verify_tts")
@patch("pipeline.pipeline.editor.asyncio.run")
def test_generate_tts_retries_on_bad_verification(mock_run, mock_verify, tmp_path: Path):
    """If verify_tts fails, _generate_tts retries up to 3 times."""
    audio = tmp_path / "seg.mp3"
    mock_run.side_effect = _close_coro

    # First 2 calls fail verification, 3rd passes
    mock_verify.side_effect = [
        (False, 0.3, "мусор"),
        (False, 0.4, "ещё мусор"),
        (True, 0.85, "правильный текст"),
    ]

    _generate_tts("правильный текст", audio, engine="elevenlabs", voice_id="v1")

    assert mock_run.call_count == 3
    assert mock_verify.call_count == 3


@patch("pipeline.pipeline.editor.verify_tts", return_value=(False, 0.2, "мусор"))
@patch("pipeline.pipeline.editor.asyncio.run")
def test_generate_tts_exits_after_max_retries(mock_run, mock_verify, tmp_path: Path):
    """After 3 failed verifications, _generate_tts calls sys.exit."""
    audio = tmp_path / "seg.mp3"
    mock_run.side_effect = _close_coro

    with pytest.raises(SystemExit):
        _generate_tts("нормальный текст", audio, engine="elevenlabs", voice_id="v1")

    assert mock_run.call_count == 3


@patch("pipeline.pipeline.editor.verify_tts")
@patch("pipeline.pipeline.editor.asyncio.run")
def test_generate_tts_skips_verification_for_non_elevenlabs(mock_run, mock_verify, tmp_path: Path):
    """Verification only runs for elevenlabs engine."""
    audio = tmp_path / "seg.mp3"
    mock_run.side_effect = _close_coro

    _generate_tts("text", audio, engine="edge", voice_id=None)

    mock_run.assert_called_once()
    mock_verify.assert_not_called()


# --- _get_duration ---


@patch("pipeline.pipeline.editor._run", return_value="5.250000")
def test_get_duration_parses_ffprobe(mock_run, tmp_path: Path):
    result = _get_duration(tmp_path / "test.mp4")
    assert result == 5.25
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffprobe"
    assert str(tmp_path / "test.mp4") in cmd


# --- _add_branding ---


@patch("pipeline.pipeline.editor._run")
def test_add_branding_uses_separate_images(mock_run, tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "intro.png").write_bytes(b"\x89PNG")
    (assets / "outro.png").write_bytes(b"\x89PNG")

    with patch("pipeline.pipeline.editor.ASSETS_DIR", assets):
        intro, outro = _add_branding(tmp_path)

    assert intro == tmp_path / "brand_intro.mp4"
    assert outro == tmp_path / "brand_outro.mp4"
    assert mock_run.call_count == 2

    # First call uses intro.png, second uses outro.png
    intro_cmd = mock_run.call_args_list[0][0][0]
    outro_cmd = mock_run.call_args_list[1][0][0]
    assert str(assets / "intro.png") in intro_cmd
    assert str(assets / "outro.png") in outro_cmd


@patch("pipeline.pipeline.editor._run")
def test_add_branding_falls_back_to_intro_for_outro(mock_run, tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "intro.png").write_bytes(b"\x89PNG")
    # No outro.png

    with patch("pipeline.pipeline.editor.ASSETS_DIR", assets):
        _add_branding(tmp_path)

    # Both calls should use intro.png
    for c in mock_run.call_args_list:
        assert str(assets / "intro.png") in c[0][0]


def test_add_branding_returns_none_when_no_assets(tmp_path: Path):
    with patch("pipeline.pipeline.editor.ASSETS_DIR", tmp_path):
        intro, outro = _add_branding(tmp_path)
    assert intro is None
    assert outro is None


# --- _apply_watermark ---


@patch("pipeline.pipeline.editor._run")
def test_apply_watermark_calls_ffmpeg(mock_run, tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "watermark.png").write_bytes(b"\x89PNG")

    with patch("pipeline.pipeline.editor.ASSETS_DIR", assets):
        _apply_watermark(tmp_path / "in.mp4", tmp_path / "out.mp4")

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "overlay=W-w-20:H-h-20" in cmd


def test_apply_watermark_copies_when_no_asset(tmp_path: Path):
    src = tmp_path / "in.mp4"
    dst = tmp_path / "out.mp4"
    src.write_bytes(b"video data")

    with patch("pipeline.pipeline.editor.ASSETS_DIR", tmp_path / "empty"):
        _apply_watermark(src, dst)

    assert dst.read_bytes() == b"video data"


# --- build (smoke test) ---


def _fake_copy(src, dst):
    """Create a fake output file so build() can stat it."""
    Path(dst).write_bytes(b"fake")


@patch("pipeline.pipeline.editor.shutil.copy2", side_effect=_fake_copy)
@patch("pipeline.pipeline.editor._run")
@patch("pipeline.pipeline.editor._generate_tts")
@patch("pipeline.pipeline.editor._get_duration", return_value=3.0)
def test_build_creates_correct_segment_count(mock_dur, mock_tts, mock_run, mock_copy, tmp_path: Path):
    """build() calls ffmpeg the right number of times for 2 video + 1 freeze segments."""
    raw = tmp_path / "raw-recording.mov"
    raw.write_bytes(b"fake video")

    config = EditConfig(
        mk_dir=tmp_path,
        segments=[
            VideoSegment("seg1", 0, 5, 1.0, "Text one"),
            VideoSegment("seg2", 5, 10, 4.0, "Text two"),
        ],
        freeze_segments=[
            FreezeSegment("freeze1", "Freeze text"),
        ],
    )

    with patch("pipeline.pipeline.editor.ASSETS_DIR", tmp_path / "no-assets"):
        build(config)

    # TTS called for: seg1, seg2 (video segments) + freeze1
    assert mock_tts.call_count == 3
    # _run called for: 2x cut+speed, 2x mux, 1x freeze-frame extract,
    # 1x freeze video, 1x freeze mux, 1x concat, plus _get_duration calls
    assert mock_run.call_count > 5


@patch("pipeline.pipeline.editor.shutil.copy2", side_effect=_fake_copy)
@patch("pipeline.pipeline.editor._run")
@patch("pipeline.pipeline.editor._generate_tts")
@patch("pipeline.pipeline.editor._get_duration", return_value=3.0)
def test_build_no_shell_in_commands(mock_dur, mock_tts, mock_run, mock_copy, tmp_path: Path):
    """All ffmpeg commands must be lists, not strings (no shell=True)."""
    raw = tmp_path / "raw-recording.mov"
    raw.write_bytes(b"fake video")

    config = EditConfig(
        mk_dir=tmp_path,
        segments=[VideoSegment("seg1", 0, 5, 1.0, "Text")],
    )

    with patch("pipeline.pipeline.editor.ASSETS_DIR", tmp_path / "no-assets"):
        build(config)

    for c in mock_run.call_args_list:
        cmd = c[0][0]
        assert isinstance(cmd, list), f"Command must be list, got: {type(cmd)}"
        assert all(isinstance(arg, str) for arg in cmd), f"All args must be str: {cmd}"
