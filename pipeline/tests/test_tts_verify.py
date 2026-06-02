"""Tests for TTS verification via Whisper."""

from pipeline.pipeline.tts_verify import normalize_text, word_match_score


def test_normalize_removes_punctuation():
    assert normalize_text("Ключ — это пропуск.") == "ключ это пропуск"


def test_normalize_removes_dashes_and_commas():
    assert normalize_text("Раз, два — три!") == "раз два три"


def test_normalize_collapses_whitespace():
    assert normalize_text("  слово   два  ") == "слово два"


def test_word_match_identical():
    assert word_match_score("ключ это пропуск", "ключ это пропуск") == 1.0


def test_word_match_partial():
    # 2 из 3 слов совпали
    score = word_match_score("ключ это пропуск", "ключ мусор пропуск")
    assert 0.6 < score < 0.7


def test_word_match_garbage():
    score = word_match_score(
        "ключ это пропуск",
        "оттому был союкочинайку",
    )
    assert score < 0.3


def test_word_match_empty_transcript():
    assert word_match_score("ключ это пропуск", "") == 0.0


def test_word_match_empty_original():
    assert word_match_score("", "что-то") == 0.0
