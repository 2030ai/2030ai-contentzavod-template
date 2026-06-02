# Pipeline

Python-модули для технической части контент-завода: извлечение кадров, подготовка текста, TTS, проверка озвучки и сборка видео через FFmpeg.

Полный процесс описан в `../docs/guides/content-pipeline.md`.

## Модули

| Модуль | Назначение |
|---|---|
| `pipeline/editor.py` | Нарезка raw-видео, speed, TTS, freeze segments, branding, concat |
| `pipeline/frames.py` | Извлечение кадров из видео для анализа агентом |
| `pipeline/text_prep.py` | Фонетические замены и предупреждения для TTS |
| `pipeline/tts.py` | ElevenLabs, Yandex SpeechKit, Edge TTS |
| `pipeline/tts_verify.py` | Whisper-проверка TTS-аудио |

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,elevenlabs,verify]"
brew install ffmpeg
```

Минимально для разработки:

```bash
pip install -e ".[dev]"
```

## Переменные окружения

Скопировать шаблон в корне репозитория:

```bash
cp ../.env.example ../.env
```

Основные переменные:

- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `ELEVENLABS_BASE_URL` или `ELEVENLABS_PROXY_URL` (опционально)
- `YANDEX_SPEECHKIT_API_KEY` (опционально)

Если ключей нет, для черновиков можно использовать `tts_engine="edge"`.

## Тесты

```bash
python -m pytest tests/ -q
```
