"""Tests for TTS text preprocessor."""

from pipeline.pipeline.text_prep import preprocess_for_tts


def test_replaces_ide():
    assert "и-дэ-йе" in preprocess_for_tts("Это IDE на базе VS Code")


def test_replaces_vs_code():
    assert "ВиЭс код" in preprocess_for_tts("Это IDE на базе VS Code")


def test_replaces_cursor():
    assert "Курсор" in preprocess_for_tts("Открываем Cursor")


def test_replaces_python():
    assert "Пайтон" in preprocess_for_tts("код на Python")


def test_replaces_keyboard_shortcut():
    result = preprocess_for_tts("Нажимаем Command+N")
    assert "кома́нд" in result
    assert "Эн" in result


def test_full_step_text():
    original = "Открываем редактор Cursor. Это IDE на базе VS Code, специально заточенный под работу с ИИ."
    result = preprocess_for_tts(original)
    assert "Cursor" not in result
    assert "IDE" not in result
    assert "VS Code" not in result
    # ИИ остаётся — Yandex SpeechKit справляется сам
    assert "ИИ" in result


def test_preserves_plain_russian():
    text = "Создаём новый файл и сохраняем его."
    assert preprocess_for_tts(text) == text
