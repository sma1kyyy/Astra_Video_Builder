# Руководство по развёртыванию

Это руководство покрывает три сценария:
- **Локальная установка** — CLI без Docker (Linux, macOS, Windows)
- **Веб-сервис** — Screenshot Mode через браузер (Docker Compose)
- **Только Celery-очередь** — фоновый рендер через CLI с флагом `--queue`

---

## Требования

| Компонент           | Версия           | Обязателен для                                                  |
| ------------------- | ---------------- | --------------------------------------------------------------- |
| Python              | 3.13+            | всё                                                             |
| uv                  | любая актуальная | всё                                                             |
| ffmpeg              | 5.0+             | оба режима                                                      |
| tesseract           | 4.0+             | smart-аннотации (OCR), AI-генератор (screenshot)                |
| gpu-screen-recorder | любая            | Live Recording на Wayland                                       |
| Docker + Compose    | 24+ / 2.20+      | веб-сервис                                                      |
| Chrome или Firefox  | актуальная       | Live Recording, AI-генератор для live mode (headless)           |
| LLM API ключ        | OpenAI-совместимый | AI-генератор (если фича нужна)                                |

---

## Linux

### 1. Системные зависимости

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install -y ffmpeg tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
```

**Fedora:**
```bash
sudo dnf install -y ffmpeg tesseract tesseract-langpack-rus
```

**Arch Linux:**
```bash
sudo pacman -S ffmpeg tesseract tesseract-data-rus tesseract-data-eng
```

### 2. gpu-screen-recorder (только для Wayland)

Если вы используете Wayland-сессию (Hyprland, GNOME, KDE Plasma) и планируете Live Recording:
```bash
# Проверьте тип сессии
echo $XDG_SESSION_TYPE
```

Если вывод `wayland` — установите gpu-screen-recorder согласно [официальной инструкции](https://git.dec05eba.com/gpu-screen-recorder/).

На Xorg достаточно ffmpeg — дополнительных утилит не нужно.

### 3. Установка проекта

```bash
git clone https://gitflic.ru/project/student-projects/aa-video-builder.git
cd aa-video-builder

# Установка uv (если ещё нет)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env

# Установка зависимостей
uv sync

# Активация окружения
source .venv/bin/activate
```

### 4. Настройка окружения

```bash
cp .env.example .env
```

Откройте `.env` и заполните:
```
YANDEX_API_KEY=your_api_key_here   # нужен только для TTS
AA_LOG_LEVEL=INFO
```

### 5. Проверка установки

```bash
python -m compileall core engines
uv run python - <<'PY'
from core.parser import parse
v = parse('examples/screenshot/screenshot_minimal.yaml')
print('OK:', v.metadata.mode, len(v.acts), 'актов')
PY
```

---

## macOS

### 1. Системные зависимости

Установите [Homebrew](https://brew.sh/) если ещё нет, затем:
```bash
brew install ffmpeg tesseract tesseract-lang
```

### 2. Разрешение на запись экрана (только для Live Recording)

Перед первым запуском Live Recording откройте:
```
System Settings → Privacy & Security → Screen Recording
```
Добавьте туда ваш терминал (Terminal, iTerm2) или IDE и **полностью перезапустите** приложение.

Без этого разрешения ffmpeg будет молча писать чёрный кадр.

### 3. Установка проекта

```bash
git clone https://gitflic.ru/project/student-projects/aa-video-builder.git
cd aa-video-builder

# Установка uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установка зависимостей
uv sync

# Активация окружения
source .venv/bin/activate
```

### 4. Настройка окружения

```bash
cp .env.example .env
# Откройте .env в редакторе и заполните YANDEX_API_KEY
```

### 5. Проверка установки

```bash
ffmpeg -version
tesseract --version
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
```

---

## Windows

### 1. Системные зависимости

**Python 3.13+** — скачайте с [python.org](https://www.python.org/downloads/). При установке отметьте галочку **«Add Python to PATH»**.

**ffmpeg** — установите через winget:
```powershell
winget install -e --id Gyan.FFmpeg
```
Или скачайте вручную с [ffmpeg.org](https://ffmpeg.org/download.html) и добавьте папку `bin` в переменную среды `PATH`.

**Tesseract** (для OCR, опционально) — скачайте установщик с [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). При установке отметьте языки Russian и English. Добавьте путь установки в `PATH`.

Проверьте в новом терминале:
```powershell
ffmpeg -version
tesseract --version
```

### 2. Установка uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Установка проекта

```powershell
git clone https://gitflic.ru/project/student-projects/aa-video-builder.git
cd aa-video-builder

python -m uv sync
.venv\Scripts\Activate.ps1
```

Если появляется ошибка про политику выполнения скриптов:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 4. Настройка окружения

```powershell
Copy-Item .env.example .env
# Откройте .env в блокноте и заполните YANDEX_API_KEY
```

### 5. Проверка установки

```powershell
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output
```

---

## Веб-сервис (Docker Compose)

Веб-сервис запускает Screenshot Mode через браузер. Live Recording через веб недоступен — запись экрана требует физического дисплея.

### Требования

- Docker 24+
- Docker Compose 2.20+

### Запуск

```bash
# Клонируйте репозиторий (если ещё не сделали)
git clone https://gitflic.ru/project/student-projects/aa-video-builder.git
cd aa-video-builder

# Скопируйте .env
cp .env.example .env
# При необходимости заполните YANDEX_API_KEY в .env

# Запуск всего стека: redis + worker + web
docker compose up --build
```

После запуска откройте браузер: **http://localhost:8000**

### Состав стека

| Сервис   | Роль                                      |
| -------- | ----------------------------------------- |
| `redis`  | Брокер и backend для Celery               |
| `worker` | Celery-воркер, выполняет задачи рендера   |
| `web`    | FastAPI-приложение + статический фронтенд |

### Параллельность

Количество одновременных задач рендера задаётся флагом `--concurrency` у воркера в `docker-compose.yml`:
```yaml
command: ["celery", "-A", "core.queue.tasks", "worker", "--loglevel=info", "--concurrency=2"]
```

Измените `2` на нужное значение и пересоберите: `docker compose up --build`.

### Остановка

```bash
docker compose down
```

Данные (ассеты, готовые видео) хранятся в Docker volume `aavb-data` и не удаляются при остановке.

Для полной очистки включая данные:
```bash
docker compose down -v
```

---

## Только Celery-очередь (без веб-сервиса)

Если нужен фоновый рендер через CLI без поднятия полного веб-стека:

```bash
# Запустить только redis и worker
docker compose up -d redis worker

# Поставить задачу в очередь
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output --queue

# Поставить задачу и дождаться результата
uv run python main.py -f examples/screenshot/screenshot_minimal.yaml -o output --queue --wait

# Проверить статус задачи
uv run python main.py -o output --task-id <task_id>
```

---

## Переменные окружения

| Переменная              | По умолчанию              | Описание                                                                                       |
| ----------------------- | ------------------------- | ---------------------------------------------------------------------------------------------- |
| `YANDEX_API_KEY`        | —                         | API-ключ Yandex SpeechKit. Обязателен только при использовании TTS                             |
| `AA_LOG_LEVEL`          | `INFO`                    | Уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR`                                       |
| `CELERY_BROKER_URL`     | `redis://redis:6379/0`    | URL брокера Celery                                                                             |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1`    | URL backend Celery для хранения статусов                                                       |
| `AAVB_WORK_DIR`         | `web/backend/_work`       | Рабочий каталог веб-сервиса (ассеты, скрипты, output)                                          |
| `LLM_API_KEY`           | —                         | API-ключ LLM-провайдера для AI-генератора. Без него endpoint `/api/generator/generate` → 503  |
| `LLM_BASE_URL`          | `https://api.openai.com/v1` | OpenAI-совместимый base URL                                                                  |
| `LLM_MODEL`             | `gpt-4o-mini`             | Модель. Рекомендуется `claude-opus-4.7` через OpenAI-совместимый прокси                       |
| `LLM_VISION_ENABLED`    | `false`                   | Резерв на будущее (Vision-LLM по скриншотам)                                                   |
| `GENERATOR_RATE_LIMIT`  | `10/minute`               | slowapi-формат, лимит на endpoint `/api/generator/generate`                                    |

---

## Типичные проблемы при установке

**`ffmpeg: command not found`** — ffmpeg не установлен или не добавлен в PATH. Проверьте установку командой `ffmpeg -version` в новом терминале.

**`ModuleNotFoundError`** после `uv sync` — виртуальное окружение не активировано. Выполните `source .venv/bin/activate` (Linux/macOS) или `.venv\Scripts\Activate.ps1` (Windows).

**`docker: command not found`** — Docker не установлен. Установите [Docker Desktop](https://www.docker.com/products/docker-desktop/).

**Порт 8000 занят** — поменяйте порт в `docker-compose.yml`: `"8001:8000"` вместо `"8000:8000"`.

Остальные проблемы — в [FAQ](Troubleshooting_Guide.md).