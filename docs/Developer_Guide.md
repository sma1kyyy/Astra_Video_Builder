<!-- инструкция для расширения функциональности -->
# Руководство разработчика

## архитектура кода
- `core/` — парсер, схемы, ошибки
- `engines/screenshot/` — screenshot пайплайн
- `engines/live/` — live модули (wip)
- `web/backend/` — FastAPI-обёртка над screenshot mode (`app/main.py`, `app/jobs.py`, `app/schemas.py`, `app/blocks.py`)
- `web/frontend/` — статический SPA-конструктор (отдаётся через `StaticFiles`)
- `web/Dockerfile`, `docker-compose.yml` — мульти-стейдж сборка и оркестрация
- `tests/` (включая `tests/web/`) — pytest-сьют
- `docs/` — документация

## как добавить новое поле в yaml
1. добавить поле в нужную schema в `core/schemas/`
2. добавить валидацию в `core/parser.py`
3. добавить обработку в engine
4. обновить `docs/Script_Format_Specification.md`
5. добавить тест

## стиль кода
- комментарии пишем по понятиям
- минимизируем что-то нереальное в парсере
- ошибки делаем явными и полезными

## локальные проверки перед коммитом
```bash
python -m compileall core engines web
pytest -q
```

## как добавить блок в web-конструктор
1. описать блок (`BlockSpec`) и поля (`BlockField`) в `web/backend/app/blocks.py` — фронт перегенерит форму автоматически по `GET /api/blocks`;
2. добавить соответствующую pydantic-модель в `web/backend/app/schemas.py` (валидация payload);
3. дополнить `to_yaml()` так, чтобы итоговый словарь укладывался в формат `core/parser.py`;
4. добавить тест в `tests/web/`.

## web-сервис локально
Web ставит задачи в Celery, поэтому нужны Redis + воркер.

```bash
# вариант 1 — всё через docker compose
docker compose up --build

# вариант 2 — локально
docker run -d --rm -p 6379:6379 redis:7-alpine
uv run celery -A core.queue.tasks worker --loglevel=info --concurrency=2 &
uv run uvicorn web.backend.app.main:app --reload --port 8000
```

Переменные: `AAVB_WORK_DIR`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.

В тестах celery работает в `task_always_eager=True` поверх `memory://` брокера — Redis для `pytest tests/web/` не нужен.
 