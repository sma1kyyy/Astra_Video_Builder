<!-- пошаговое руководство для создания первого видео в каждом режиме -->
# Руководство для начинающих.
Это пошаговый старт для человека, который впервые видит проект.
результат: вы получите готовый mp4 из screenshot-сценария.

1. подготовка окружения. Проверьте зависимости:
```bash
python --version
uv --version
ffmpeg -version
```

Рекомендуется установить OCR-движок:
```bash
tesseract --version
```

2. установка
```bash
git clone https://gitflic.ru/project/student-projects/aa-video-builder.git
cd aa-video-builder
uv sync
source .venv/bin/activate
```

Скопируйте `.env.example` в `.env` и заполните `YANDEX_API_KEY` (нужен только если используете TTS).

## Screenshot Mode. Введение.
### 1. первый рендер
```bash
mkdir -p output
uv run python main.py -f examples/screenshot_minimal.yaml -o output
```

после выполнения проверьте выход:
```bash
ls -lah output
```

### 2. что вы получите
- `<title>.mp4` — итоговое видео.
- `<title>_ocr.json` — ocr metadata (если включён ocr_target metadata/both).
- `output/audio_cache/*.wav` — кэш tts.

### 3. настройка сценария
редактируйте `examples/screenshot_minimal.yaml`:
- меняйте `path` на свои изображения,
- включайте `subtitles` и стили,
- добавляйте smart аннотации через `target_text`.

### 4. обязательные проверки
```bash
python -m compileall cli core engines
uv run python - <<'PY'
from core.parser import parse
v = parse('examples/screenshot_minimal.yaml')
print(v.metadata.mode, len(v.acts), len(v.acts[0].scenes))
PY
```

### 5. если что-то пошло не так
[смотрите](Troubleshooting_Guide.md)

## Live Recording. Введение.
1. Создайте каталог, например `data`, в котором вы будете хранить yaml-скрипт, скриншоты и итоговое видео.
2. Создайте в этом каталоге файл `script.yaml`.
3. Вставьте в него любой пример из [примеров](Example_Scripts.md) для режима Live Recording Mode.
4. Запустите команду:
   ```bash
   uv run python main.py -f data/script.yaml -o data
   ```
   (или `./main.py -f data/script.yaml -o data` — у `main.py` есть shebang).
5. Дождитесь отключения браузера. Даже если кажется, что съёмка завершилась, монтаж итогового видео ещё может идти.
6. Итоговое видео сохраняется в указанный каталог `-o`.

[Подробная информация по режиму Live Recording](Live_Recording_Mode_Guide.md)

[Столкнулись с проблемами?](Troubleshooting_Guide.md)