# Настройка окружения

Применять при создании нового проекта из шаблона или при первом запуске пайплайна.

## Python и FFmpeg

```bash
cd pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,elevenlabs,verify]"
brew install ffmpeg
```

Если production TTS не нужен, можно поставить только dev:

```bash
pip install -e ".[dev]"
```

## Переменные окружения

Скопировать шаблон:

```bash
cp .env.example .env
```

Заполнить только нужные значения:

- `ELEVENLABS_API_KEY` — production TTS.
- `ELEVENLABS_VOICE_ID` — выбранный голос. Если пусто, используется дефолт в коде.
- `ELEVENLABS_BASE_URL` или `ELEVENLABS_PROXY_URL` — опционально для совместимых gateway/proxy.
- `YANDEX_SPEECHKIT_API_KEY` — опциональный fallback TTS.
- `OPENAI_API_KEY` — опциональные иллюстрации или дополнительные проверки.

## Видимость `.env`

`.env` должен быть виден человеку в IDE, но не должен попадать в git и контекст AI-агентов.

Проверить:

- `.gitignore` содержит `.env`, `.env.local`, `.env.*.local`.
- `.cursorignore` скрывает `.env`, но не скрывает `.env.example`.
- `.vscode/settings.json` не прячет `.env`, если пользователь хочет редактировать его из VS Code.

## Проверка

```bash
cd pipeline
source .venv/bin/activate
python -m pytest tests/ -q
```
