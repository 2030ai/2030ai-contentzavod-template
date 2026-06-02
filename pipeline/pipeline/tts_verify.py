"""Verify TTS audio by transcribing with Whisper and comparing to original text."""

import re
from pathlib import Path

_whisper_model = None


def _get_model():
    """Lazy-load Whisper tiny model (singleton)."""
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model("tiny")
    return _whisper_model


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_match_score(original: str, transcript: str) -> float:
    """Compute fraction of original words found in transcript.

    Returns 0.0–1.0. Order-independent: checks that each word
    from original appears in transcript at least once.
    """
    orig_words = normalize_text(original).split()
    if not orig_words:
        return 0.0
    if not transcript.strip():
        return 0.0
    trans_words = normalize_text(transcript).split()
    matched = sum(1 for w in orig_words if w in trans_words)
    return matched / len(orig_words)


def verify_tts(audio_path: Path, original_text: str, threshold: float = 0.7) -> tuple[bool, float, str]:
    """Transcribe audio with Whisper and compare to original text.

    Returns:
        (passed, score, transcript) where passed is True if score >= threshold.
    """
    model = _get_model()
    result = model.transcribe(str(audio_path), language="ru")
    transcript = result["text"].strip()
    score = word_match_score(original_text, transcript)
    return score >= threshold, score, transcript
