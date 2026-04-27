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