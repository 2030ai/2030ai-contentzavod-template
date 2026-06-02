# 2030ai ContentZavod Template

Шаблон конвейера для производства обучающих материалов об ИИ-инструментах:
от идеи до сценария, записи экрана, монтажа, озвучки, статьи и финальной проверки.

Репозиторий рассчитан на работу через Claude Code/Codex/Cursor skills. Это не отдельное приложение: агент ведёт пользователя по пайплайну, сохраняет артефакты в файлы, а человек подключается только в точках контроля и записи экрана.

## Что умеет

- Генерировать и валидировать идеи мастер-классов через синтетическую фокус-группу.
- Делать сценарий, ТЗ на запись и чек-листы качества.
- Собирать видео через `ffmpeg`: нарезка, ускорение генераций, TTS-озвучка, интро/аутро, watermark.
- Проверять ElevenLabs TTS через Whisper и повторять генерацию при расхождении.
- Превращать видео в статью со скриншотами, метаданными и копируемыми промптами.
- Проводить аудит проекта через отдельный `audit` skill.

## Быстрый старт

1. Создайте репозиторий из этого шаблона.

2. Установите окружение:

   ```bash
   cd pipeline
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev,elevenlabs,verify]"
   brew install ffmpeg
   ```

3. Настройте ключи:

   ```bash
   cp .env.example .env
   # заполните .env, если используете ElevenLabs или OpenAI
   ```

4. Запустите агентскую среду и вызовите skill:

   ```text
   /mk <тема или конкретная идея мастер-класса>
   ```

5. Артефакты появятся в `content/<slug>/`: `brief.md`, `scenario.md`, `recording-brief.md`, `voiceover-script.md`, `edit.py`, `final.mp4`, `article.md`, `metadata.yaml`.

## Skills

| Skill | Назначение |
|---|---|
| `mk` | Основной конвейер: идея -> фокус-группа -> сценарий -> запись -> монтаж -> статья -> QC |
| `audit` | Полная ревизия проекта: пути, факты, документы, мысленный прогон `/mk` |

Canonical skills лежат в `.agents/skills/`. Для совместимости добавлены symlink-зеркала в `.claude/skills/`, `.codex/skills/`, `.cursor/skills/`.

## Структура

```text
├── .agents/skills/      # canonical skills: mk, audit
├── content/             # создаваемые мастер-классы и README со статусами
├── docs/                # концепция, архитектура, гайды, история
├── pipeline/            # Python-модуль монтажа, TTS, frames, тесты
├── .env.example         # шаблон переменных окружения
├── AGENTS.md            # правила для AI-агентов
└── CLAUDE.md            # symlink на AGENTS.md
```

## Документация

- `docs/concept.md` — миссия, аудитория, уровни, границы.
- `docs/guides/content-pipeline.md` — обзор 11 шагов.
- `docs/guides/pipeline-phase1-validation.md` — валидация идеи.
- `docs/guides/pipeline-phase2-production.md` — производство видео и статьи.
- `docs/guides/environment-setup.md` — переменные окружения и локальная настройка.
- `pipeline/README.md` — Python-модули, установка и тесты.

## Лицензия

MIT — см. `LICENSE`.
