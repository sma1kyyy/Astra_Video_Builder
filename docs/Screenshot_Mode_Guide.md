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
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
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
  
дополнительно поддерживаются типы аннотаций:
- `line`
- `arrow`
- `darrow`

для `line/arrow/darrow` направление задаётся строго координатами `start -> end`.

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
v = parse('examples/screenshot/screenshot_minimal.yaml')
print(v.metadata.mode, len(v.acts))
PY
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
```

## 10. checkpointing (восстановление после сбоя)
В screenshot mode автоматически ведётся checkpoint:
- `output/.<title>_checkpoint.json`
- `output/.scene_cache/scene_<N>.mp4`

Если процесс прерван, повторный запуск той же команды продолжит рендер с последней успешно обработанной сцены.

## 11. запуск через Web-сервис и через очередь
В каталоге `web/` лежит HTTP-обёртка над screenshot mode (FastAPI + статический фронт-конструктор).
Рендер выполняется не в потоках web-процесса, а в Celery-воркере поверх Redis (см. `core/queue/`),
поэтому web остаётся отзывчивым, а параллельность настраивается через `--concurrency` воркера.

Compose-файл (`docker-compose.yml` в корне) поднимает все три сервиса разом — `redis`, `worker`, `web`:
```bash
docker compose up --build
# UI: http://localhost:8000/   ·   API: http://localhost:8000/api/...
```

> **Важно про CLI и `--queue`.** Флаг `--queue` у `main.py` отправляет задачу в Celery,
> а значит требует поднятых `redis` + `worker`. Без них поставленная задача просто
> останется висеть, а итоговый рендер не запустится. Если рендер через очередь не
> нужен — запускай CLI без `--queue`, тогда `process_video()` отработает синхронно
> в текущем процессе и Docker не понадобится.

Локально без докера (для разработки веба) нужно поднять Redis отдельно (`docker run -p 6379:6379 redis:7-alpine`),
а затем:
```bash
# терминал 1 — воркер
uv run celery -A core.queue.tasks worker --loglevel=info --concurrency=2
# терминал 2 — web
uv run uvicorn web.backend.app.main:app --reload --port 8000
```

Что доступно:
- `GET /api/blocks` — описание блоков конструктора (metadata / scene / annotation), используемое фронтом для авто-генерации форм.
- `POST /api/assets` (multipart) — загрузка одного (`file=`) или нескольких (`files=`) скриншотов; после загрузки путь подставляется в сцену по имени файла.
- `POST /api/scripts/preview` — pydantic-валидация payload и возврат собранного YAML без запуска рендера.
- `POST /api/scripts/parse` — загрузить готовый YAML (`.yml/.yaml`); парсер `core/parser.py` валидирует, бэк нормализует `scene.path` к basename и возвращает `{payload, yaml, missing_assets}`. Используется фронтом и для режима «редактор YAML», и для авто-заполнения конструктора при перетаскивании файла.
- `POST /api/jobs` — постановка задачи `render_video_task` в Celery; возвращает `job_id` (он же celery `task_id`).
- `GET /api/jobs[/{id}]` — статус (маппится из celery state: PENDING→queued, STARTED→running, SUCCESS→done, FAILURE→failed, REVOKED→cancelled), список выходных файлов.
- `POST /api/jobs/{id}/cancel` — `celery_app.control.revoke(task_id, terminate=True)`.
- `GET /api/jobs/{id}/files/{name}` — скачать готовое видео / sidecar-метадату.

Frontend (`web/frontend/`) — статический SPA на vanilla JS без сборки:
- стартовый экран — две карточки: «Загрузить YAML» / «Конструктор», ниже общая форма для скриншотов;
- свап тёмной/светлой темы (☀/🌙) в левом верхнем углу, выбор хранится в `localStorage` + cookie `aavb-theme`;
- hamburger-кнопка в правом верхнем углу открывает выезжающий drawer со списком задач (вкладки «Активные» — кнопка отмены / «Завершённые» — кнопки скачивания файлов);
- глобальный drag-n-drop YAML по всей странице: в режиме конструктора — заполняет поля; иначе — открывает встроенный YAML-редактор с подсветкой;
- ошибки парсинга/валидации показываются всплывающим toast снизу; принимаются только расширения `.yml/.yaml/.YML/.YAML`.

Переменные окружения:
- `AAVB_WORK_DIR` (по умолчанию `web/backend/_work`) — где живут ассеты, сгенерированные YAML, output-каталоги и реестр celery-задач.
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — Redis URL (по умолчанию `redis://redis:6379/0,1`).
- Параллельность регулируется флагом `--concurrency` Celery-воркера (по умолчанию `2`).

Live Recording через web-сервис не запускается осознанно: запись экрана требует физического дисплея и `gpu-screen-recorder` / `avfoundation`, чего в headless-контейнере нет.