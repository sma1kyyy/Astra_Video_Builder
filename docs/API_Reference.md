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
- `-f, --file` — путь до yaml-сценария.
- `-o, --output` — путь до каталога результата.

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

