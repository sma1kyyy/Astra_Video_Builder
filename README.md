# СИСТЕМА ГЕНЕРАЦИИ ДЕМОНСТРАЦИОННЫХ РОЛИКОВ НА ОСНОВЕ СКРИПТОВ
Этот проект из себя представляет систему модулей для генерации демонстрационных видео-роликов Astra Automation с использованием YAML-скриптов.

Эта система позволит сотрудникам создавать видео-ролики, презентующие новую технологию или обучающий материал, гораздо быстрее, чем это было бы при ручном монтаже.

**В ключевые особенности входит:**
- Поддержка двух режимов записи: Live Recording и Screenshot Mode
- Функционал для воспроизведения аудио с использованием TTS и субтитров к нему (работают в обоих режимах)
- Множество эффектов монтажа, такие как переходы между кадрами, наложение различных изображений или вставка музыки
- HTTP-сервис в `web/` (FastAPI + статический фронт-конструктор) для запуска screenshot mode из браузера. Запуск: `docker compose up --build`. Подробности — в [Screenshot Mode Guide §11](docs/Screenshot_Mode_Guide.md) и [API Reference](docs/API_Reference.md).
- **AI-генератор YAML-скриптов** (карточка «AI-генератор» во фронтенде или `POST /api/generator/generate`): описываете сценарий словами, LLM возвращает готовый YAML. Для live mode под капотом поднимается headless Chrome, LLM реально проходит сценарий через tool-calling и проверяет селекторы перед возвратом. Для screenshot mode подключается OCR. Требует `LLM_API_KEY` в `.env` — см. [API Reference §AI-генератор](docs/API_Reference.md#ai-генератор-yaml-скриптов).

# Как использовать
## Необходимые требования к окружению
- [Python версии 3.13+](https://www.python.org/downloads/release/python-31311/)
- [Пакетный менеджер UV для установки зависимостей](https://docs.astral.sh/uv/getting-started/installation/)
- [FFMPEG](https://www.ffmpeg.org/) — нужен и для Live Recording, и для Screenshot Mode (под капотом MoviePy вызывает ffmpeg при сборке итогового видео).
- [tesseract](https://github.com/tesseract-ocr/tesseract) (`tesseract-ocr` + `tesseract-ocr-rus`) — для smart-аннотаций и для OCR-контекста AI-генератора. Без него AI-генератор работает, но без распознавания текста на скриншотах.
- (Опционально) `LLM_API_KEY` в `.env` — для AI-генератора. Поддерживается любой OpenAI-совместимый провайдер; по умолчанию — `gpt-4o-mini`, рекомендуется `claude-opus-4.7` через прокси. Полный список переменных: [Deployment Guide §Переменные окружения](docs/Deployment_Guide.md#переменные-окружения).
##### Дополнительно для режима Live Recording
- [Утилита gpu-screen-recorder для записи Wayland-сессий](https://git.dec05eba.com/gpu-screen-recorder/)

    *Примечание. Для Wayland (Hyprland, GNOME, KDE Plasma) используется gpu-screen-recorder. Поддерживает скрытие курсора (`-cursor no`).*

    *Для macOS используется встроенный в ffmpeg backend `avfoundation`. Перед первым запуском обязательно выдайте вашему терминалу / IDE разрешение `System Settings → Privacy & Security → Screen Recording` и полностью перезапустите его — иначе запись пойдёт чёрным кадром без ошибок.*
- [Chrome Browser](https://www.google.com/intl/ru_ru/chrome/) или [Firefox](https://www.mozilla.org/firefox/)

    *Выбор браузера задаётся через поле `browser: chrome|firefox` в `metadata` YAML-скрипта (по умолчанию `chrome`).*

## Установка
Склонируйте репозиторий в каталог с проектом или установите последнюю версию релиза
```
git clone https://gitflic.ru/project/student-projects/aa-video-builder.git
```
После этого установите зависимости:
```
uv sync
```
Активируйте виртуальное окружение:
```bash
source .venv/bin/activate
```
Для windows:
```
python -m uv sync
```

## Очередь задач (Celery + Redis)
Очередь нужна в двух случаях:
- запуск рендера через web-сервис (`docker compose up --build`);
- запуск CLI с флагом `--queue` (фоновая обработка одного или нескольких скриптов).

Без очереди CLI отрабатывает локально, синхронно, прямо в текущем процессе:
```bash
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
```

Если хочется фоновый рендер через Celery — поднимаем `redis` и `worker`:
```bash
docker compose up -d redis worker
```
Поставить задачу в очередь:
```bash
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output --queue
```
Поставить и дождаться результата:
```bash
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output --queue --wait
```
Проверить статус уже поставленной задачи:
```bash
uv run python main.py -o output --task-id <task_id>
```
По умолчанию используются переменные:
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://redis:6379/1`
Пошаговые инструкции по развёртыванию для Linux/macOS/Windows доступны в отдельном документе:
- [Deployment Guide](docs/Deployment_Guide.md)

Для использования перейдите в [руководство для начинающих](docs/Getting_Started_Guide.md).

# Документация
1. [Руководство по использованию CLI или API](docs/API_Reference.md)
2. [Руководство модулей системы](docs/Architecture_Document.md)
3. [Руководство разработчика](docs/Developer_Guide.md)
4. [Примеры YAML-скриптов](docs/Example_Scripts.md)
5. [Руководство режима Live Recording](docs/Live_Recording_Mode_Guide.md)
6. [Руководство Screenshot Mode](docs/Screenshot_Mode_Guide.md)
7. [Руководство по оптимизации](docs/Performance_Tuning.md)
8. [Руководство по написанию YAML-скриптов](docs/Script_Format_Specification.md)
9. [FAQ](docs/Troubleshooting_Guide.md)
10.  [Руководство по развёртыванию на Linux/macOS/Windows](docs/Deployment_Guide.md)