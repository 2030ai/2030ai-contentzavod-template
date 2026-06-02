"""Text-to-speech generation: ElevenLabs, Yandex SpeechKit, Edge TTS."""

import os
from pathlib import Path

import edge_tts
import requests
from dotenv import load_dotenv

from pipeline.pipeline.text_prep import preprocess_for_tts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "pipeline" / ".env", override=False)

# --- ElevenLabs ---

ELEVENLABS_MODEL = "eleven_multilingual_v2"

# --- Yandex SpeechKit ---

YANDEX_TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

YANDEX_VOICE_MAP = {
    ("ru", "male"): "zahar",
    ("ru", "female"): "jane",
}

# --- Edge TTS (fallback) ---

EDGE_VOICE_MAP = {
    ("ru", "male"): "ru-RU-DmitryNeural",
    ("ru", "female"): "ru-RU-SvetlanaNeural",
    ("en", "male"): "en-US-GuyNeural",
    ("en", "female"): "en-US-JennyNeural",
}


def resolve_engine(engine: str = "auto", voice_id: str | None = None) -> str:
    """Resolve "auto" to an available TTS engine."""
    if engine != "auto":
        return engine
    if os.environ.get("ELEVENLABS_API_KEY") and (
        voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    ):
        return "elevenlabs"
    if os.environ.get("YANDEX_SPEECHKIT_API_KEY"):
        return "yandex"
    return "edge"


async def generate_voice(
    text: str,
    output_path: Path,
    language: str = "ru",
    speaker: str = "male",
    engine: str = "auto",
    voice_id: str | None = None,
) -> None:
    """Generate speech audio file from text.

    Args:
        text: Text to synthesize.
        output_path: Where to save the audio file.
        language: Language code ("ru", "en").
        speaker: Voice gender ("male", "female").
        engine: "elevenlabs", "yandex", "edge", or "auto".
            auto priority: elevenlabs (if key+voice) > yandex (if key) > edge.
        voice_id: ElevenLabs voice ID override.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    engine = resolve_engine(engine, voice_id)

    processed_text = preprocess_for_tts(text, engine=engine)

    if engine == "elevenlabs":
        _generate_elevenlabs(processed_text, output_path, voice_id)
    elif engine == "yandex":
        _generate_yandex(processed_text, output_path, language, speaker)
    else:
        await _generate_edge(processed_text, output_path, language, speaker)


ELEVENLABS_SPEED = 1.1


def _generate_elevenlabs(
    text: str, output_path: Path, voice_id: str | None = None
) -> None:
    from elevenlabs import ElevenLabs, VoiceSettings

    api_key = os.environ["ELEVENLABS_API_KEY"]
    resolved_voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    if not resolved_voice_id:
        raise RuntimeError("Set ELEVENLABS_VOICE_ID or pass voice_id to EditConfig.")

    base_url_env = (
        os.environ.get("ELEVENLABS_BASE_URL")
        or os.environ.get("ELEVENLABS_PROXY_URL")
    )
    proxy_user = os.environ.get("ELEVENLABS_PROXY_USER", "")
    proxy_pass = os.environ.get("ELEVENLABS_PROXY_PASS", "")

    if base_url_env and proxy_user and proxy_pass:
        # http://user:pass@host:port -> used by httpx for basic auth
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(base_url_env)
        base_url = urlunparse(
            parsed._replace(
                netloc=f"{proxy_user}:{proxy_pass}@{parsed.hostname}:{parsed.port}"
            )
        )
    else:
        base_url = base_url_env

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = ElevenLabs(**client_kwargs)
    audio_iter = client.text_to_speech.convert(
        voice_id=resolved_voice_id,
        text=text,
        model_id=ELEVENLABS_MODEL,
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(speed=ELEVENLABS_SPEED),
    )
    # SDK returns an iterator of bytes chunks
    with open(output_path, "wb") as f:
        for chunk in audio_iter:
            f.write(chunk)


def _generate_yandex(
    text: str, output_path: Path, language: str, speaker: str
) -> None:
    api_key = os.environ["YANDEX_SPEECHKIT_API_KEY"]
    voice = YANDEX_VOICE_MAP.get((language, speaker), "filipp")

    response = requests.post(
        YANDEX_TTS_URL,
        headers={"Authorization": f"Api-Key {api_key}"},
        data={
            "text": text,
            "lang": "ru-RU" if language == "ru" else "en-US",
            "voice": voice,
            "speed": "1.15",
            "format": "mp3",
        },
    )
    response.raise_for_status()
    output_path.write_bytes(response.content)


async def _generate_edge(
    text: str, output_path: Path, language: str, speaker: str
) -> None:
    voice = EDGE_VOICE_MAP.get((language, speaker), "ru-RU-DmitryNeural")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))
