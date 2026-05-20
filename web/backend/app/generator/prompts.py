from __future__ import annotations

from pathlib import Path
from typing import List, Literal

_EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "examples"

ModeName = Literal["screenshot", "live"]


def _read_example(relative: str) -> str:
    path = _EXAMPLES_DIR / relative
    return path.read_text(encoding="utf-8")


_SCREENSHOT_FIELDS_SPEC = """\
Поля YAML для screenshot mode:

metadata:
  title: <slug, только латиница/цифры/._-, без пробелов>
  resolution: <WxH, например 1920x1080>
  mode: screenshot                  # обязательно
  fps: <int, 24 рекомендуется>
  language: ru | en

acts:
  act_1:
    name: <строка>
    scenes:
      scene_1:
        name: <строка>
        path: <относительный путь к ассету, например input/screen1.png>
        duration: <float, секунды>   # обязательно
        tts: <строка, текст для озвучки>   # опционально
        voice: zahar | jane                # опционально
        subtitles: true|false              # опционально
        subtitle_style: classic|minimal|contrast|cinematic
        subtitle_font_size: <int, по умолчанию 40>
        subtitle_max_chars: <int, по умолчанию 96>
        subtitle_bg_opacity: <float 0..1>
        subplace: up|center|down            # позиция субтитров
        transition: without|slideRight|slideLeft|slideUp|slideDown|blackout
        transpeed: <float, длительность перехода в секундах>
        annotations:                        # опционально, для подсветки участков скриншота
          annotation_1:
            type: square | arrow | line | darrow
            transparency: <float 0..1>
            start_x: <int>
            start_y: <int>
            end_x: <int>
            end_y: <int>
            wait: <float, задержка до старта аннотации>
            duration: <float, длительность показа>
            target_text: <строка>           # если задан — координаты подстраиваются под найденный OCR-текст
            auto_padding: <int, отступ от bbox в пикселях>
            auto_from: left|right|top|bottom  # для arrow — откуда направлять
            ocr: true|false                  # включить OCR-валидацию координат
            ocr_lang: rus+eng
            ocr_min_conf: <float 0..1>
            ocr_target: overlay|metadata|both
            text: <строка>                    # дополнительный текст внутри square
"""


_LIVE_FIELDS_SPEC = """\
Поля YAML для live recording mode:

metadata:
  title: <slug>
  resolution: <WxH>
  mode: live                          # обязательно
  browser: chrome | firefox
  cursor: true | false
  fps: <int, 30 рекомендуется>
  language: ru | en
  save_files: true | false

acts:
  act_1:
    name: <строка>
    scenes:
      scene_1:
        name: <строка>
        duration: <float, секунды>     # обязательно
        tts: <строка, текст для озвучки>
        voice: zahar | jane
        actions:                       # ОБЯЗАТЕЛЬНО первое действие первой сцены — type: navigate
          action_1:
            type: navigate | click | input | wait | scrollUp | scrollDown | scrollTo
            url: <URL>                  # для navigate
            selector: <XPath>           # для click | input | scrollTo
            text: <строка>              # для input
            duration: <int>             # для wait, секунды
            point: <int>                # для scrollUp | scrollDown
            behavior: auto | smooth     # опционально для scroll
            wait: <float>               # пауза перед действием, default 1
"""


_COMMON_RULES = """\
ВАЖНЫЕ ПРАВИЛА:
1. Возвращай ТОЛЬКО валидный YAML без markdown-обёрток, без пояснений до или после.
2. Структура: на верхнем уровне ровно два ключа — `metadata` и `acts`.
3. Ключи актов и сцен формата `act_<N>`, `scene_<N>`, `annotation_<N>`, `action_<N>` (N — целое число, начиная с 1).
4. Все строки на русском, если language=ru. TTS-тексты грамотные, естественные.
5. Не выдумывай поля, которых нет в спецификации. Лишние поля приведут к ошибке парсера.
6. Если пользователь указал параметры (голос, разрешение, fps) — используй их.
7. title должен быть slug'ом: только латиница, цифры, `.`, `_`, `-`. Без пробелов.
"""


def _format_ocr_block(ocr_per_asset: dict[str, list[dict]] | None) -> str:
    if not ocr_per_asset:
        return ""
    lines = ["", "OCR-данные распознанные на скриншотах (используй target_text/координаты из этих данных):"]
    for filename, items in ocr_per_asset.items():
        if not items:
            lines.append(f"  {filename}: текст не распознан")
            continue
        lines.append(f"  {filename}:")
        for item in items[:30]:
            text = item.get("text", "").replace("\n", " ")
            bbox = item.get("bbox", [])
            conf = item.get("conf", 0)
            lines.append(f"    - \"{text}\" bbox={bbox} conf={conf}")
    return "\n".join(lines)


def _format_asset_descriptions(descriptions: dict[str, str] | None) -> str:
    if not descriptions:
        return ""
    lines = ["", "Подсказки пользователя по скриншотам:"]
    for filename, text in descriptions.items():
        if text.strip():
            lines.append(f"  {filename}: {text.strip()}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def build_screenshot_prompt(
    *,
    user_description: str,
    asset_filenames: List[str],
    ocr_per_asset: dict[str, list[dict]] | None = None,
    asset_descriptions: dict[str, str] | None = None,
    voice: str = "jane",
    language: str = "ru",
    resolution: str = "1920x1080",
    fps: int = 24,
) -> list[dict]:
    minimal = _read_example("screenshot/screenshot_minimal.yaml")
    extended = _read_example("screenshot/screenshot_extended_demo.yaml")

    system = (
        "Ты — генератор YAML-скриптов для системы aa-video-builder (screenshot mode).\n"
        "Твоя задача — на основе описания пользователя и распознанного текста на скриншотах\n"
        "сгенерировать корректный YAML-скрипт для рендера демонстрационного видео.\n\n"
        + _SCREENSHOT_FIELDS_SPEC
        + "\n"
        + _COMMON_RULES
        + "\n\nПРИМЕР 1 (минимальный):\n"
        + minimal
        + "\n\nПРИМЕР 2 (расширенный, с TTS, субтитрами, аннотациями):\n"
        + extended
    )

    ocr_block = _format_ocr_block(ocr_per_asset)
    desc_block = _format_asset_descriptions(asset_descriptions)

    user_lines = [
        f"Сценарий: {user_description.strip()}",
        "",
        "Параметры:",
        f"  голос TTS: {voice}",
        f"  язык: {language}",
        f"  разрешение: {resolution}",
        f"  fps: {fps}",
        "",
        "Доступные ассеты (используй ровно эти имена в поле path сцен, путь относительный):",
    ]
    for name in asset_filenames:
        user_lines.append(f"  - input/{name}")

    user_lines.extend([ocr_block, desc_block])
    user = "\n".join(line for line in user_lines if line is not None)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_live_spec_block(
    *,
    user_description: str,
    start_url: str,
    voice: str = "jane",
    browser: str = "chrome",
    language: str = "ru",
    resolution: str = "1920x1080",
    fps: int = 30,
) -> str:
    minimal = _read_example("live/live_minimal.yaml")
    extended = _read_example("live/live_extended.yaml")

    return (
        "СПЕЦИФИКАЦИЯ YAML (live recording mode):\n\n"
        + _LIVE_FIELDS_SPEC
        + "\n"
        + _COMMON_RULES
        + "\n8. Первое действие первой сцены ОБЯЗАНО быть type: navigate с указанным url.\n"
        + "9. XPath-селекторы используй только реально существующие в DOM. \n"
        + "   Не строй селекторы вида //input[@placeholder='X' or @type='Y'] — это галлюцинация.\n"
        + "\nПРИМЕР 1 (минимальный):\n"
        + minimal
        + "\n\nПРИМЕР 2 (расширенный, все типы действий):\n"
        + extended
        + "\n\nЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ:\n"
        + user_description.strip()
        + "\n\nПАРАМЕТРЫ:\n"
        + f"  стартовый URL: {start_url}\n"
        + f"  браузер: {browser}\n"
        + f"  голос TTS: {voice}\n"
        + f"  язык: {language}\n"
        + f"  разрешение: {resolution}\n"
        + f"  fps: {fps}\n"
    )


def build_live_prompt(
    *,
    user_description: str,
    start_url: str,
    voice: str = "jane",
    browser: str = "chrome",
    language: str = "ru",
    resolution: str = "1920x1080",
    fps: int = 30,
) -> list[dict]:
    system = (
        "Ты — генератор YAML-скриптов для системы aa-video-builder (live recording mode).\n"
        "Твоя задача — на основе описания пользователя сгенерировать корректный YAML-скрипт,\n"
        "по которому браузер выполнит сценарий, а с экрана будет записано видео.\n"
        "Возвращай ТОЛЬКО валидный YAML без markdown-обёрток."
    )
    user = build_live_spec_block(
        user_description=user_description,
        start_url=start_url,
        voice=voice,
        browser=browser,
        language=language,
        resolution=resolution,
        fps=fps,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
