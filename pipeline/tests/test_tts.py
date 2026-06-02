import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.pipeline.tts import generate_voice, _generate_elevenlabs, resolve_engine


@pytest.mark.asyncio
async def test_generate_voice_edge_creates_mp3(tmp_path: Path):
    """Edge TTS generates an audio file from Russian text."""
    output_path = tmp_path / "step-01.mp3"

    mock_communicate = MagicMock()
    mock_communicate.save = MagicMock()

    async def fake_save(path: str):
        Path(path).write_bytes(b"\xff" * 2000)

    mock_communicate.save = fake_save

    with patch("pipeline.pipeline.tts.edge_tts.Communicate", return_value=mock_communicate):
        await generate_voice(
            text="Привет, это тестовая озвучка.",
            output_path=output_path,
            engine="edge",
        )

    assert output_path.exists()
    assert output_path.stat().st_size > 1000


@pytest.mark.asyncio
async def test_generate_voice_yandex_calls_api(tmp_path: Path):
    """Yandex SpeechKit sends correct API request."""
    output_path = tmp_path / "step-01.mp3"

    mock_response = MagicMock()
    mock_response.content = b"\xff" * 2000
    mock_response.raise_for_status = MagicMock()

    with patch.dict("os.environ", {"YANDEX_SPEECHKIT_API_KEY": "test-key"}), \
         patch("pipeline.pipeline.tts.requests.post", return_value=mock_response) as mock_post:
        await generate_voice(
            text="Привет, это тестовая озвучка.",
            output_path=output_path,
            engine="yandex",
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["data"]["voice"] == "zahar"
    assert call_kwargs.kwargs["data"]["format"] == "mp3"
    assert output_path.exists()


@pytest.mark.asyncio
async def test_auto_engine_picks_yandex_when_key_present(tmp_path: Path):
    """Auto engine selects yandex when API key is set."""
    output_path = tmp_path / "step-01.mp3"

    mock_response = MagicMock()
    mock_response.content = b"\xff" * 2000
    mock_response.raise_for_status = MagicMock()

    with patch.dict("os.environ", {"YANDEX_SPEECHKIT_API_KEY": "test-key"}), \
         patch("pipeline.pipeline.tts.requests.post", return_value=mock_response):
        await generate_voice(text="Тест", output_path=output_path)

    assert output_path.exists()


@pytest.mark.asyncio
async def test_auto_engine_falls_back_to_edge(tmp_path: Path):
    """Auto engine falls back to Edge TTS when no Yandex key."""
    output_path = tmp_path / "step-01.mp3"

    mock_communicate = MagicMock()

    async def fake_save(path: str):
        Path(path).write_bytes(b"\xff" * 2000)

    mock_communicate.save = fake_save

    with patch.dict("os.environ", {}, clear=True), \
         patch("pipeline.pipeline.tts.edge_tts.Communicate", return_value=mock_communicate):
        await generate_voice(text="Тест", output_path=output_path)

    assert output_path.exists()


def test_generate_elevenlabs_calls_sdk(tmp_path: Path):
    """ElevenLabs engine calls SDK with correct params through proxy."""
    output_path = tmp_path / "step-01.mp3"

    mock_audio = [b"\xff" * 1000, b"\x00" * 500]
    mock_client = MagicMock()
    mock_client.text_to_speech.convert.return_value = iter(mock_audio)

    env = {
        "ELEVENLABS_API_KEY": "test-key",
        "ELEVENLABS_VOICE_ID": "voice-id",
        "ELEVENLABS_PROXY_URL": "http://proxy:8443",
        "ELEVENLABS_PROXY_USER": "user",
        "ELEVENLABS_PROXY_PASS": "pass",
    }
    with patch.dict("os.environ", env), \
         patch("elevenlabs.ElevenLabs", return_value=mock_client) as mock_cls:
        _generate_elevenlabs("Тест озвучки", output_path)

    mock_cls.assert_called_once_with(
        api_key="test-key",
        base_url="http://user:pass@proxy:8443",
    )
    mock_client.text_to_speech.convert.assert_called_once()
    call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
    assert call_kwargs["voice_id"] == "voice-id"
    assert call_kwargs["text"] == "Тест озвучки"
    assert call_kwargs["model_id"] == "eleven_multilingual_v2"
    assert output_path.exists()
    assert output_path.stat().st_size == 1500


@pytest.mark.asyncio
async def test_auto_engine_picks_elevenlabs_when_key_and_voice(tmp_path: Path):
    """Auto engine selects elevenlabs when API key and voice are set."""
    output_path = tmp_path / "step-01.mp3"

    mock_audio = [b"\xff" * 1000]
    mock_client = MagicMock()
    mock_client.text_to_speech.convert.return_value = iter(mock_audio)

    env = {
        "ELEVENLABS_API_KEY": "test-key",
        "ELEVENLABS_VOICE_ID": "voice-id",
    }
    with patch.dict("os.environ", env, clear=True), \
         patch("elevenlabs.ElevenLabs", return_value=mock_client) as mock_cls:
        await generate_voice(text="Тест", output_path=output_path)

    assert output_path.exists()
    mock_cls.assert_called_once_with(api_key="test-key")
    mock_client.text_to_speech.convert.assert_called_once()


def test_resolve_engine_needs_voice_for_elevenlabs():
    """Auto skips ElevenLabs when API key exists but voice is missing."""
    with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"}, clear=True):
        assert resolve_engine("auto") == "edge"
