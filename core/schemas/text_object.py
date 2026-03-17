from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict, model_validator
from dataclasses import fields
from typing import List, Optional, Literal
from core.schemas.ComponentObject import ComponentObject

@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class TextObject(ComponentObject):
    """текстовый блок для показа на экране"""
    # обязательные поля
    text: str = Field(
        ...,
        description="Сам текст."
    )
    start_x: int = Field(
        ...,
        description="Начальное положение по X.",
        ge=0
    )
    start_y: int = Field(
        ...,
        description="Начальное положение по Y.",
        ge=0
    )
    size: int = Field(
        ...,
        description="Размер текста.",
        ge=12
    )
    
    # опциональные поля
    font: str = Field(
        default="DejaVu-Sans",
        description="Название шрифта."
    )
    wait: float = Field(
        default=0.0,
        description="задержка появления (сек)"
    )
    duration: float = Field(
        default=0.0,
        description="длительность показа (0 = до конца сцены)"
    )
    
    @model_validator(mode="after")
    def post_init(self):
        # валидация
        assert self.text.strip(), "text не может быть пустым"
