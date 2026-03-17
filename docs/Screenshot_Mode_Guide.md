<!-- инструкция по использованию режима снимков экрана, подготовке
снимков, добавлению аннотаций -->
# Руководство по режиму Screenshot Mode

## 1. зачем этот режим
screenshot mode - это режим, в котором видео собирается из заранее подготовленных изображений (png/jpg) без live браузерной записи.
он идеально подходит для учебных роликов, стабильных демо и офлайн-пайплайнов.

## 2. как устроен пайплайн
1. `main.py` принимает yaml и папку вывода.
2. `core/parser.py` валидирует сценарий и собирает объектную модель.
3. `engines/screenshot/screenshot_engine.py`:
  - строит сцены из фона и оверлеев,
  - добавляет tts,
  - рендерит субтитры,
  - применяет аннотации (вручную и smart-режим),
  - запускает OCR и сохраняет sidecar metadata,
  - экспортирует mp4.

## 3. запуск
```bash
mkdir -p output
uv run python main.py -f examples/screenshot_minimal.yaml -o output
```

## 4. структура screenshot сцены
минимум:
```yaml
scene_1:
  path: input/screen1.png
  duration: 4
```

расширенный вариант:
```yaml
scene_1:
  name: templates page
  path: input/screen1.png
  duration: 5
  tts: "это раздел шаблонов"
  subtitles: true
  subtitle_style: contrast
  subtitle_font_size: 40
  subtitle_max_chars: 96
  subtitle_bg_opacity: 0.6
  annotations:
    annotation_1:
      type: square
      transparency: 0.25
      target_text: "Templates"
      auto_padding: 18
      ocr: true
      ocr_target: both
```

## 5. smart annotations (авто-координаты)
теперь можно не прописывать координаты руками, если у аннотации задан `target_text`.
движок сделает так:
1. прогонит OCR по кадру,
2. найдёт наиболее похожий текст,
3. вычислит bbox,
4. расширит bbox через `auto_padding` и `auto_expand_*`.

это сильно сокращает ручную разметку и уменьшает ошибки координат.

### параметры smart-режима
- `target_text`: текст, который нужно найти на скриншоте.
- `target_index`: если совпадений несколько, выбор по индексу (0 — лучший матч).
- `auto_padding`: общий запас вокруг найденного текста.
- `auto_expand_width`, `auto_expand_height`: дополнительное расширение.
- `auto_from` (для arrow): откуда начинать стрелку (`auto|left|right|top|bottom|center`).

## 6. стили субтитров
поддерживаются стили:
- `classic`: классическая подложка + текст.
- `minimal`: лёгкий текст без тяжёлого фона.
- `contrast`: усиленная плашка для светлых интерфейсов.
- `cinematic`: широкая lower-third зона.

настройки:
- `subtitle_font_size`
- `subtitle_max_chars`
- `subtitle_bg_opacity`

## 7. ocr в screenshot mode
ocr можно включить на square-аннотациях:
- `ocr: true`
- `ocr_lang: rus+eng`
- `ocr_min_conf: 0.35`
- `ocr_target: overlay|metadata|both`

что получается:
- overlay-текст в кадре (если распознано),
- sidecar json рядом с видео (`*_ocr.json`) для логов и отладки.

## 8. практические советы
1. делайте одинаковое разрешение исходных скринов.
2. проверяйте контраст текста интерфейса до OCR.
3. используйте `contrast`/`cinematic` стили для длинных фраз.
4. включайте smart-annotation сначала на один элемент и проверяйте попадание.
5. храните ассеты и yaml рядом по понятной структуре (`input/`, `examples/`).

## 9. быстрый чек-лист перед рендером
```bash
python -m compileall cli core engines
uv run python - <<'PY'
from core.parser import parse
v = parse('examples/screenshot_minimal.yaml')
print(v.metadata.mode, len(v.acts))
PY
uv run python main.py -f examples/screenshot_minimal.yaml -o output
```
