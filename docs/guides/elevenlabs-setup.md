# Настройка ElevenLabs

ElevenLabs используется как production TTS для естественной озвучки видеоуроков.

## Шаги

1. Создать аккаунт на `elevenlabs.io`.
2. Выбрать тариф, который поддерживает нужный объём символов и voice features.
3. Создать или выбрать голос в разделе Voices.
4. Скопировать API key.
5. Узнать Voice ID выбранного голоса.
6. Записать значения в `.env`:

```bash
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

## Опциональный gateway/proxy

Если используется совместимый gateway или proxy, задать одно из:

```bash
ELEVENLABS_BASE_URL=https://example.com
ELEVENLABS_PROXY_URL=https://example.com
ELEVENLABS_PROXY_USER=
ELEVENLABS_PROXY_PASS=
```

Без этих переменных SDK обращается к стандартному ElevenLabs API.

## Проверка качества

Пайплайн проверяет ElevenLabs-аудио через Whisper:

```bash
cd pipeline
pip install -e ".[verify]"
```

Если Whisper слышит текст с низким совпадением, `editor.py` повторяет TTS до 3 раз. После трёх неудач нужно переформулировать текст озвучки.

Правила произношения: `docs/guides/voiceover-writing.md`.
