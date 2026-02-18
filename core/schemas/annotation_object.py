from dataclasses import dataclass, fields
from typing import Optional

from core.schemas.ComponentObject import ComponentObject


@dataclass
class AnnotationObject(ComponentObject):
    type: str = "square"
    transparency: float = 0.0
    start_x: int = 0
    start_y: int = 0
    end_x: int = 100
    end_y: int = 100
    wait: float = 0.0
    duration: float = 0.0
    label: Optional[str] = None
    text: Optional[str] = None

    # OCR MVP
    ocr: bool = False
    ocr_lang: str = "rus+eng"
    ocr_min_conf: float = 0.0
    ocr_target: str = "overlay"  # overlay | metadata | both

    @classmethod
    def get_static_attributes(cls):
        return [f.name for f in fields(cls)]

    def __post_init__(self):
        # Авто-коррекция: если перепутали старт и конец, просто меняем их местами
        if self.start_x > self.end_x:
            self.start_x, self.end_x = self.end_x, self.start_x

        if self.start_y > self.end_y:
            self.start_y, self.end_y = self.end_y, self.start_y

        # Нулевой размер фиксим до 1px
        if self.start_x == self.end_x:
            self.end_x += 1
        if self.start_y == self.end_y:
            self.end_y += 1

        # Ограничение прозрачности
        self.transparency = max(0.0, min(1.0, float(self.transparency)))

        # Проверка типа
        if self.type not in ["square", "arrow"]:
            self.type = "square"

        # OCR defaults/bounds
        self.ocr_min_conf = float(self.ocr_min_conf)
        self.ocr_min_conf = max(0.0, min(1.0, self.ocr_min_conf))

        if self.ocr_target not in ["overlay", "metadata", "both"]:
            self.ocr_target = "overlay"