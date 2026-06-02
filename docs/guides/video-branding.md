# Брендинг видео

`editor.py` автоматически добавляет интро, аутро и watermark, если соответствующие ассеты есть в `pipeline/assets/`.

## Ассеты

| Файл | Назначение |
|---|---|
| `intro.png` | 2-секундная заставка в начале |
| `outro.png` | 2-секундная заставка в конце |
| `watermark.png` | Watermark в правом нижнем углу |
| `logo-4x.png` | Исходное лого для генерации ассетов |

В шаблоне можно заменить эти файлы на бренд своей школы, компании или автора. Если ассета нет, `editor.py` пропускает соответствующий шаг.

## Порядок сборки

1. Нарезать и ускорить сегменты.
2. Совместить видео с озвучкой.
3. Создать intro/outro clips из PNG.
4. Склеить: intro -> segments -> outro.
5. Наложить watermark.

## Watermark

Команда, которую реализует `editor.py`:

```bash
ffmpeg -y -i video.mp4 -i pipeline/assets/watermark.png \
  -filter_complex "overlay=W-w-20:H-h-20" \
  -c:v libx264 -preset fast -crf 22 -c:a copy \
  video_branded.mp4
```
