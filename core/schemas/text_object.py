from dataclasses import dataclass, field
from typing import Optional
from core.schemas.ComponentObject import ComponentObject

@dataclass
class TextObject(ComponentObject):
    """текстовый блок для показа на экране"""
    # обязательные поля
    text: str = ""
    start_x: int = 0
    start_y: int = 0
    size: int = 48
    
    # опциональные поля
    font: str = "DejaVu-Sans"  # название шрифта
    wait: float = 0.0  # задержка появления (сек)
    duration: float = 0.0  # длительность показа (0 = до конца сцены)
    
    def __post_init__(self):
        # валидация
        if not self.text.strip():
            raise ValueError("text не может быть пустым")
        if self.size < 12:
            self.size = 12  # минимальный размер
        if self.start_x < 0 or self.start_y < 0:
            raise ValueError("координаты не могут быть отрицательными")
