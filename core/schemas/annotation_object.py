from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict, model_validator
from typing import List, Optional, Literal
from dataclasses import fields
from typing import Optional

from core.schemas.ComponentObject import ComponentObject


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class AnnotationObject(ComponentObject):
    type: Literal["square", "line", "arrow", "darrow"] = Field(
        default="square",
        description=(
            "Тип аннотации. "
            "square — прямоугольник; "
            "line — прямая линия; "
            "arrow — стрелка в одну сторону; "
            "darrow — двунаправленная стрелка."
        ),
    )
    transparency: float = Field(
        default=0.0,
        description="Прозрачность от 0 (непрозрачно) до 1 (невидимо).",
        ge=0,
        le=1,
    )
    start_x: int = Field(default=0, description="Начало по X.")
    start_y: int = Field(default=0, description="Начало по Y.")
    end_x: int = Field(default=0, description="Конец по X.")
    end_y: int = Field(default=0, description="Конец по Y.")
    wait: float = Field(
        default=0.0, description="Ожидание перед появлением (сек)."
    )
    duration: float = Field(
        default=0.0, description="Длительность аннотации (0 = до конца сцены)."
    )
    label: Optional[str] = Field(
        default=None, description="Текстовый лейбл рядом с аннотацией."
    )
    text: Optional[str] = Field(
        default=None, description="Текст внутри аннотации (только type=square)."
    )

    # Smart annotation
    target_text: Optional[str] = Field(
        default=None,
        description="Текст для поиска на скриншоте (smart-режим).",
    )
    target_index: int = Field(
        default=0,
        description="Индекс совпадения при нескольких найденных.",
        ge=0,
    )
    auto_padding: int = Field(
        default=16,
        description="Отступ вокруг найденного текста (px).",
        ge=0,
    )
    auto_expand_width: int = Field(
        default=12,
        description="Дополнительное расширение bbox по ширине.",
        ge=0,
    )
    auto_expand_height: int = Field(
        default=8,
        description="Дополнительное расширение bbox по высоте.",
        ge=0,
    )
    auto_from: Literal["auto", "center", "left", "right", "top", "bottom"] = Field(
        default="auto",
        description="Направление старта стрелки для type=arrow.",
    )

    #Fallback поведение
    has_manual_coords: bool = Field(
        default=False,
        description="Были ли переданы ручные координаты.",
    )
    use_manual_fallback: bool = Field(
        default=True,
        description="Использовать ручные координаты если smart-поиск не нашёл.",
    )

    # OCR параметры
    ocr: Optional[bool] = Field(
        default=None,
        description="Запускать OCR на области (только type=square).",
    )
    ocr_lang: str = Field(
        default="rus+eng",
        description="Языки Tesseract.",
    )
    ocr_min_conf: float = Field(
        default=0.0,
        description="Минимальный порог уверенности OCR (0..1).",
        ge=0.0,
        le=1.0,
    )
    ocr_target: Literal["overlay", "metadata", "both"] = Field(
        default="overlay",
        description=(
            "overlay — показать текст в кадре; "
            "metadata — записать в JSON sidecar; "
            "both — и то и то."
        ),
    )

    @classmethod
    def get_static_attributes(cls):
        return [f.name for f in fields(cls)]

    @model_validator(mode="after")
    def post_init(self) -> "AnnotationObject":
        # Нормализуем координаты для типов, где важна область (square)
        # Для line/arrow/darrow координаты — это реальные start→end, менять не нужно.
        if self.type == "square":
            if self.has_manual_coords or not self.target_text:
                if self.start_x > self.end_x:
                    self.start_x, self.end_x = self.end_x, self.start_x
                if self.start_y > self.end_y:
                    self.start_y, self.end_y = self.end_y, self.start_y
                if self.start_x == self.end_x:
                    self.end_x += 1
                if self.start_y == self.end_y:
                    self.end_y += 1

        # OCR доступен только для square
        if self.ocr and self.type != "square":
            self.ocr = False

        return self

# prev. version
# @dataclass
# class AnnotationObject(ComponentObject):
#     type: str = "square"
#     transparency: float = 0.0
#     start_x: int = 0
#     start_y: int = 0
#     end_x: int = 100
#     end_y: int = 100
#     wait: float = 0.0
#     duration: float = 0.0
#     label: Optional[str] = None
#     text: Optional[str] = None

#     # OCR MVP
#     ocr: bool = False
#     ocr_lang: str = "rus+eng"
#     ocr_min_conf: float = 0.0
#     ocr_target: str = "overlay"  # overlay | metadata | both

#     @classmethod
#     def get_static_attributes(cls):
#         return [f.name for f in fields(cls)]

#     def __post_init__(self):
#         # Авто-коррекция: если перепутали старт и конец, просто меняем их местами
#         if self.start_x > self.end_x:
#             self.start_x, self.end_x = self.end_x, self.start_x

#         if self.start_y > self.end_y:
#             self.start_y, self.end_y = self.end_y, self.start_y

#         # Нулевой размер фиксим до 1px
#         if self.start_x == self.end_x:
#             self.end_x += 1
#         if self.start_y == self.end_y:
#             self.end_y += 1

#         # Ограничение прозрачности
#         self.transparency = max(0.0, min(1.0, float(self.transparency)))

#         # Проверка типа
#         if self.type not in ["square", "arrow"]:
#             self.type = "square"

#         # OCR defaults/bounds
#         self.ocr_min_conf = float(self.ocr_min_conf)
#         self.ocr_min_conf = max(0.0, min(1.0, self.ocr_min_conf))

#         if self.ocr_target not in ["overlay", "metadata", "both"]:
#             self.ocr_target = "overlay"