<!-- # CLI
Для создания видео используется скрипт **main.py**. Ему передаются 2 обязательных параметра: 
- file - путь до YAML-скрипта
- output - путь до каталога, куда будет сохранено видео

Режим, название итогового видео и прочие параметры передаются в YAML-скрипте.

*Пример:*
```
uv run python main.py -f path/to/script.yaml -o path/to/dir
``` -->
# Руководство по взаимодействию (API)

## CLI

точка входа: `main.py`
 
### базовая команда
```bash
uv run python main.py -f <script.yaml> -o <output_dir>
```
### параметры
- `-f, --file` — путь до yaml-сценария (обязателен для запуска новой задачи).
- `-o, --output` — путь до каталога результата.
- `--queue` — поставить задачу в очередь Celery/Redis.
- `--wait` — ждать завершения queued-задачи.
- `--task-id` — проверить статус существующей queued-задачи.
- `--timeout` — таймаут ожидания queued-задачи (секунды, default: `3600`).

### пример
```bash
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
```

## screenshot mode runtime поведение
при `metadata.mode: screenshot` выполняется:
1. parser и валидация;
2. рендер сцен;
3. tts синтез и кэширование;
4. наложение субтитров;
5. рендер аннотаций (ручных и smart);
6. OCR overlay/metadata;
7. экспорт mp4.

## ключевые поля screenshot api (yaml)
- `scene.subtitle_style`: `classic|minimal|contrast|cinematic`
- `annotation.target_text`: smart поиск текста в кадре
- `annotation.ocr_*`: тонкая настройка OCR

### пример с очередью
> Требует поднятых `redis` + `worker` (`docker compose up -d redis worker`). Без них флаг `--queue` отправит задачу, но её некому будет выполнить.
```bash
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output --queue
```

### пример с ожиданием результата
```bash
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output --queue --wait --timeout 1800
```

### проверка статуса задачи
```bash
uv run python main.py -o output --task-id <task_id>
```

## queue runtime (Celery + Redis)

Для фоновых задач используется Celery worker и Redis broker/result backend.

Запуск инфраструктуры:
```bash
docker compose up -d redis worker
```

Переменные окружения:
- `CELERY_BROKER_URL` (default: `redis://redis:6379/0`)
- `CELERY_RESULT_BACKEND` (default: `redis://redis:6379/1`)

## HTTP API (web-сервис)

Реализация: `web/backend/app/main.py` (FastAPI). Используется только для screenshot mode.
Под капотом задачи рендера ставятся в Celery (`core.queue.tasks.render_video_task`) поверх Redis,
а web лишь принимает payload и опрашивает статусы через `celery_app.AsyncResult`.

Запуск стека: `docker compose up --build` (поднимает `redis`, `worker`, `web`).

### endpoints
- `GET  /api/health` — heartbeat (`{"status":"ok"}`).
- `GET  /api/blocks` — описание блоков конструктора (поля, типы, дефолты, диапазоны). Используется фронтом для генерации форм и бэком для валидации.
- `POST /api/assets` — multipart upload скриншота(ов). Принимает либо одно поле `file=<binary>`, либо несколько `files=<binary>` (bulk). Возвращает `{filename, path}` для одного файла или `{saved: [...]}` для нескольких. Имя нормализуется (только `[A-Za-z0-9._-]`).
- `GET  /api/assets` — список загруженных ассетов.
- `DELETE /api/assets/{name}` — удалить ассет.
- `POST /api/scripts/preview` — pydantic-валидация payload и возврат собранного YAML (без запуска рендера). Тело — `ScriptPayload` (см. ниже).
- `POST /api/scripts/parse` — multipart upload готового YAML-файла (`file=<.yml/.yaml>`). Парсит через `core/parser.py`, нормализует `scene.path` к basename, возвращает `{payload, yaml, missing_assets}` для подстановки в конструктор/редактор. Принимает только режим `screenshot`. На ошибки парсера — 422 с человеко-читаемым `detail`.
- `POST /api/jobs` — поставить рендер screenshot mode в очередь. Возвращает `{job_id}`. Проверяет, что все `scene.path` залиты через `/api/assets`.
- `GET  /api/jobs` / `GET /api/jobs/{id}` — список задач / статус (`queued|running|done|failed|cancelled`), хвост лога, выходные файлы.
- `POST /api/jobs/{id}/cancel` — отменить queued/running задачу.
- `GET  /api/jobs/{id}/files/{name}` — скачать файл из output-каталога задачи.

### формат ScriptPayload
```jsonc
{
  "metadata": {
    "title": "demo",          // ^[A-Za-z0-9а-яА-Я._-]+$
    "resolution": "1920x1080",// ^\d+x\d+$
    "fps": 24,                // 1..240
    "language": "ru|en",
    "description": ""
  },
  "scenes": [                 // min_length=1
    {
      "name": "scene",
      "path": "screen1.png",  // должен существовать в /api/assets
      "duration": 4.0,        // > 0
      "tts": "",
      "voice": "jane|zahar",
      "subtitles": false,
      "subtitle_style": "classic|minimal|contrast|cinematic",
      "subtitle_font_size": 40,
      "transition": "without|slideRight|slideLeft|slideUp|slideDown|blackout",
      "annotations": [
        {
          "type": "square|arrow|line|darrow",
          "transparency": 0.3,
          "start_x": 0, "start_y": 0, "end_x": 100, "end_y": 100,
          "wait": 0.0, "duration": 0.0,
          "target_text": "",     // OCR smart-цель (опционально)
          "ocr": false,
          "text": ""              // только для type=square
        }
      ]
    }
  ]
}
```

### переменные окружения сервиса
- `AAVB_WORK_DIR` (default `web/backend/_work`) — корень для assets / scripts / outputs / реестра celery-задач.
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — Redis URL (по умолчанию `redis://redis:6379/0,1`).
- Параллельность задаётся флагом `--concurrency` celery-воркера (см. `docker-compose.yml`), а не самим web-процессом.

### почему только screenshot mode
Live Recording требует физический display server и `gpu-screen-recorder` / `avfoundation`, которых в headless-контейнере нет. Web-сервис намеренно отвергает payload c `mode != screenshot`.