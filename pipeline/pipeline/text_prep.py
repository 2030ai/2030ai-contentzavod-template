"""Preprocess text for TTS: replace abbreviations and English terms with phonetic Russian."""

import re

# Общий словарь замен (работает для всех движков).
# Ключи — регулярные выражения (case-insensitive), значения — замены.
# Порядок важен: длинные фразы перед короткими ("VS Code" перед "Code").

PHONETIC_DICT: list[tuple[str, str]] = [
    # === Бренды и продукты ===
    (r"\bCursor\b", "Курсор"),
    (r"\bVS Code\b", "ВиЭс код"),
    (r"\bPerplexity Spaces\b", "Перплексити Спейсес"),
    (r"\bPerplexity\b", "Перплексити"),
    (r"\bChatGPT\b", "Чат Джи-Пи-Ти"),
    (r"\bClaude Code\b", "Клод Код"),
    (r"\bClaude\b", "Клод"),
    (r"\bGoogle Docs\b", "Гугл Докс"),
    (r"\bGoogle Sheets\b", "Гугл Шитс"),
    (r"\bGoogle Drive\b", "Гугл Драйв"),
    (r"\bNotion\b", "Ноушен"),
    (r"\bTodoist\b", "Тудуист"),
    (r"\bClickUp\b", "КликАп"),
    (r"\bAsana\b", "Асана"),
    (r"\bTrello\b", "Трелло"),
    (r"\bSlack\b", "Слэк"),
    (r"\bYouTube\b", "Ютуб"),
    (r"\bPowerPoint\b", "ПауэрПойнт"),
    (r"\bExcel\b", "Эксель"),
    (r"\bAdobe Scan\b", "Адоби Скэн"),
    (r"\bMicrosoft Lens\b", "Майкрософт Ленз"),
    (r"\bWindows\b", "Виндоус"),

    # === Аббревиатуры ===
    (r"\bIDE\b", "и-дэ-йе"),
    (r"\bAPI\b", "эй-пи-ай"),
    (r"\bTTS\b", "ти-ти-эс"),
    (r"\bPDF\b", "пи-ди-эф"),
    (r"\bOCR\b", "о-си-ар"),
    (r"\bURL\b", "УРЛ"),
    (r"\bSaaS\b", "сас"),
    (r"\bFAQ\b", "эф-эй-кью"),
    (r"\bSMM\b", "эс-эм-эм"),
    (r"\bUX\b", "ю-экс"),
    (r"\bB2B\b", "би-ту-би"),
    (r"\bH1\b", "аш один"),
    (r"\bH2\b", "аш два"),
    (r"\bH3\b", "аш три"),

    # === Технические термины ===
    (r"\bSpace\b", "Спейс"),
    (r"\bSpaces\b", "Спейсес"),
    (r"\bThread\b", "Тред"),
    (r"\bThreads\b", "Треды"),
    (r"\bPrompt\b", "Промпт"),
    (r"\bSystem Prompt\b", "Систем Промпт"),
    (r"\bPython\b", "Пайтон"),
    (r"\bDashboard\b", "Дэшборд"),
    (r"\bUpload\b", "Аплоуд"),
    (r"\bDownload\b", "Даунлоуд"),

    # === Клавиатурные сочетания (перед одиночными буквами!) ===
    (r"\bCommand\+", "кома́нд плюс "),
    (r"\bControl\+", "контрол плюс "),
    (r"\bCmd\+", "кома́нд плюс "),
    (r"\bCtrl\+", "контрол плюс "),

    # === Одиночные латинские буквы (клавиши) ===
    (r"\bN\b", "Эн"),
    (r"\bS\b", "Эс"),

    # === Файлы и код ===
    (r"\bhello\.py\b", "хэлло точка пай"),
    (r"\.py\b", " точка пай"),
    (r"\.pdf\b", " точка пи-ди-эф"),
    (r"\.docx?\b", " точка док"),
    (r"\bprint\b", "принт"),
    (r"\bHello, World!", "Хэлло, Ворлд!"),
    (r"\bhello\b", "хэлло"),
]

# Замены, которые отличаются между движками.
# Ключ — паттерн, значение — dict {engine: replacement}.
ENGINE_OVERRIDES: list[tuple[str, dict[str, str]]] = [
    (r"\bSEO\b", {"yandex": "эс-и-о", "elevenlabs": "СьЭо"}),
    (r"\bКурсор", {"yandex": "Курсор", "elevenlabs": "кур-сор"}),
    (r"(?i)\bчатджипити", {"yandex": "ЧатДжипити", "elevenlabs": "Чат ДжиПиТИ"}),
    (r"(?i)\bджипити", {"yandex": "Джипити", "elevenlabs": "ДжиПиТИ"}),
    (r"\b[Дд]ипсик", {"yandex": "дипсик", "elevenlabs": "дипсИИк"}),
    (r"\b[Дд]жемини", {"yandex": "джемини", "elevenlabs": "Джеминай"}),
    (r"\b[Кк]лауд", {"yandex": "клауд", "elevenlabs": "клод"}),
]

# Слова, которые ElevenLabs может произнести с неправильным ударением.
# Формат: (паттерн для поиска в тексте, описание проблемы).
# Валидатор предупреждает, если слово найдено и НЕ покрыто ENGINE_OVERRIDES.
ELEVENLABS_WATCHLIST: list[tuple[str, str]] = [
    (r"\bКурсор", "ударение на У вместо О — override → «кур-сор»"),
    (r"(?i)\bчатджипити", "ударение не на последнем И — override → «Чат ДжиПиТИ»"),
    (r"(?i)\bджипити", "ударение не на последнем И — override → «ДжиПиТИ»"),
    (r"\bSEO\b", "произносит «сео» — override → «СьЭо»"),
    (r"\b[Дд]ипсик", "ударение не на И — override → «дипсИИк»"),
    (r"\b[Дд]жемини", "произносит по-русски — override → «Джеминай»"),
    (r"\b[Кк]лауд", "произносит «клауд» — override → «клод»"),
    # Добавлять сюда новые проблемные слова по мере обнаружения:
    # (r"\bНовоеСлово", "описание проблемы"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in PHONETIC_DICT]
_COMPILED_OVERRIDES = [(re.compile(p, re.IGNORECASE), d) for p, d in ENGINE_OVERRIDES]
_COMPILED_WATCHLIST = [(re.compile(p), desc) for p, desc in ELEVENLABS_WATCHLIST]

# Паттерны из ENGINE_OVERRIDES — слова, которые уже исправляются автоматически.
_OVERRIDE_PATTERNS = [re.compile(p, re.IGNORECASE) for p, _ in ENGINE_OVERRIDES]


def validate_tts_text(text: str, engine: str = "elevenlabs") -> list[str]:
    """Check text for known pronunciation problems. Returns list of warnings.

    Call before TTS generation to catch issues early.
    Only checks for the specified engine (default: elevenlabs).
    """
    if engine != "elevenlabs":
        return []

    warnings = []

    # 1. Проверяем watchlist — слова с известными проблемами
    for pattern, desc in _COMPILED_WATCHLIST:
        match = pattern.search(text)
        if match:
            word = match.group()
            # Проверяем, покрыто ли уже ENGINE_OVERRIDES
            covered = any(op.search(word) for op in _OVERRIDE_PATTERNS)
            if not covered:
                warnings.append(f"⚠ «{word}»: {desc}")

    # 2. Слова с заглавной русской буквы в начале предложения — риск сдвига ударения
    #    (кроме первого слова после точки/начала текста — это нормально)
    capitals = re.findall(r"(?<!\. )(?<!^)\b[А-ЯЁ][а-яё]{3,}", text)
    for word in capitals:
        # Пропускаем если слово покрыто ENGINE_OVERRIDES
        covered = any(op.search(word) for op in _OVERRIDE_PATTERNS)
        if not covered and word not in ("Если", "Когда", "Потом", "Теперь",
                                         "Давайте", "Просим", "Видно",
                                         "Начните", "Один", "Минимум"):
            warnings.append(
                f"⚠ «{word}» — заглавная буква может сдвинуть ударение в ElevenLabs. "
                f"Если произношение ок — добавьте в ELEVENLABS_WATCHLIST как исключение."
            )

    return warnings


def preprocess_for_tts(text: str, engine: str = "yandex") -> str:
    """Replace English terms and abbreviations with phonetic Russian equivalents.

    Args:
        text: Original text.
        engine: TTS engine name ("yandex", "elevenlabs", "edge").
    """
    result = text
    for pattern, replacement in _COMPILED:
        result = pattern.sub(replacement, result)
    for pattern, replacements in _COMPILED_OVERRIDES:
        replacement = replacements.get(engine, replacements.get("yandex", ""))
        result = pattern.sub(replacement, result)
    return result
