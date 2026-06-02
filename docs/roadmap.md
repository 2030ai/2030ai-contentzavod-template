# Roadmap

Шаблон уже содержит базовый конвейер `mk`, аудит, документацию и Python-модуль монтажа.

## Готово

- 11-шаговый пайплайн: идея -> видео -> статья -> QC -> очистка.
- Фокус-группа из 8 персон.
- Видео-первичный монтаж через `edit.py` и общий `editor.py`.
- ElevenLabs TTS с Whisper-проверкой.
- Edge TTS fallback для разработки.
- Symlink-зеркала skills для Claude/Codex/Cursor.

## Ближайшие улучшения

1. Добавить пример минимального мастер-класса без приватного контента.
2. Добавить генератор `edit.py` из `voiceover-script.md`.
3. Упростить импорт пакета: `pipeline.pipeline` -> `pipeline`.
4. Добавить CLI для извлечения article screenshots из `final.mp4`.
5. Добавить GitHub Actions: tests + markdown link check.

## Возможные интеграции

- CMS/API публикация статей.
- YouTube upload.
- Автоматическое обновление `pipeline/content-registry.md`.
- Batch-режим: список тем -> серия мастер-классов.
