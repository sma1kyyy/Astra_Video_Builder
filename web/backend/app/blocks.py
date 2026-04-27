"""Constructor block definitions exposed to the frontend.

Каждый блок описывает кусок YAML-сценария (метаданные, сцена, аннотация
и т.д.) и набор полей, которые пользователь заполняет. Все модели —
pydantic, поэтому фронтенд получает их сериализованными, а бэкенд
использует те же объекты для валидации входящего payload и сборки YAML.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


FieldType = Literal["string", "text", "int", "float", "bool", "enum"]


class BlockField(BaseModel):
    """Описание одного поля внутри блока конструктора."""
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    type: FieldType
    required: bool = False
    default: Optional[Any] = None
    options: Optional[List[str]] = None
    description: str = ""
    min: Optional[float] = None
    max: Optional[float] = None


class BlockSpec(BaseModel):
    """Полное описание блока (metadata / scene / annotation / ...)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    cardinality: Literal["single", "many"]
    parent: Optional[str] = None
    fields: List[BlockField]


def _f(
    name: str,
    label: str,
    field_type: FieldType,
    *,
    required: bool = False,
    default: Any = None,
    options: List[str] | None = None,
    description: str = "",
    min: Any = None,
    max: Any = None,
) -> BlockField:
    return BlockField(
        name=name,
        label=label,
        type=field_type,
        required=required,
        default=default,
        options=options,
        description=description,
        min=min,
        max=max,
    )


METADATA_BLOCK = BlockSpec(
    id="metadata",
    title="Metadata",
    description="Параметры итогового видео.",
    cardinality="single",
    fields=[
        _f("title", "Название", "string", required=True, default="my_video"),
        _f("resolution", "Разрешение", "string", required=True, default="1920x1080"),
        _f("fps", "FPS", "int", default=24, min=1, max=120),
        _f("language", "Язык TTS", "enum", default="ru", options=["ru", "en"]),
        _f("description", "Описание", "text", default=""),
    ],
)

SCENE_BLOCK = BlockSpec(
    id="scene",
    title="Сцена",
    description="Один кадр-скриншот в видео.",
    cardinality="many",
    fields=[
        _f("name", "Имя сцены", "string", default="scene"),
        _f("path", "Путь до скриншота", "string", required=True,
           description="Имя файла из загруженных ассетов (например, screen1.png)."),
        _f("duration", "Длительность, сек", "float", default=4.0, min=0.1),
        _f("tts", "TTS-текст", "text", default=""),
        _f("voice", "Голос", "enum", default="jane", options=["jane", "zahar"]),
        _f("subtitles", "Субтитры", "bool", default=False),
        _f("subtitle_style", "Стиль субтитров", "enum", default="classic",
           options=["classic", "minimal", "contrast", "cinematic"]),
        _f("subtitle_font_size", "Размер шрифта субтитров", "int",
           default=40, min=16),
        _f("transition", "Переход", "enum", default="without",
           options=["without", "slideRight", "slideLeft", "slideUp",
                    "slideDown", "blackout"]),
    ],
)

ANNOTATION_BLOCK = BlockSpec(
    id="annotation",
    title="Аннотация",
    description="Подсветка области (square / arrow / line / darrow).",
    cardinality="many",
    parent="scene",
    fields=[
        _f("type", "Тип", "enum", default="square",
           options=["square", "arrow", "line", "darrow"]),
        _f("transparency", "Прозрачность", "float", default=0.3,
           min=0.0, max=1.0),
        _f("start_x", "X начала", "int", default=0, min=0),
        _f("start_y", "Y начала", "int", default=0, min=0),
        _f("end_x", "X конца", "int", default=100, min=0),
        _f("end_y", "Y конца", "int", default=100, min=0),
        _f("wait", "Задержка, сек", "float", default=0.0, min=0.0),
        _f("duration", "Длительность, сек", "float", default=0.0, min=0.0),
        _f("target_text", "Smart-цель (OCR)", "string", default="",
           description="Если задан — координаты ищутся по тексту через OCR. "
                       "Ручные координаты используются как fallback."),
        _f("ocr", "Использовать OCR", "bool", default=False),
        _f("text", "Подпись (только square)", "string", default=""),
    ],
)


ALL_BLOCKS: List[BlockSpec] = [METADATA_BLOCK, SCENE_BLOCK, ANNOTATION_BLOCK]
BLOCKS_BY_ID = {block.id: block for block in ALL_BLOCKS}


def list_blocks() -> List[BlockSpec]:
    """Возвращает каталог блоков для фронтенд-конструктора."""
    return ALL_BLOCKS


def find_block(block_id: str) -> Optional[BlockSpec]:
    return BLOCKS_BY_ID.get(block_id)
