from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict, model_validator
from typing import List, Optional, Literal

from core.schemas.ComponentObject import ComponentObject

@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class MetadataObject(ComponentObject):
    title: str = Field(
        ...,
        description="Название итогового видео.",
        pattern=r"^[a-zA-Z0-9а-яА-Я._\-]+$"
    )
    resolution: str = Field(
        ...,
        description="Разрешение экрана записи видео.",
        pattern=r"^\d+x\d+$"
    )
    description: Optional[str] = Field(
        default="",
        description="Описание видео для логов."
    )
    language: Literal["ru", "eng"] = Field(
        default="ru",
        description="Язык TTS."
    )
    mode: Literal["live", "screenshot"] = Field(
        default="live",
        description="Режим создания видео."
    )
    cursor: Optional[bool] = Field(
        default=False,
        description="Отображать курсор в конечной записи или нет."
    )
    fps: Optional[int] = Field(
        default=30,
        description="FPS у итогового видео.",
        gt=0
    )


    # def __init__(
    #     self,
    #     title: str,
    #     resolution: str,
    #     description="",
    #     language="ru",
    #     mode="live",
    #     cursor=True,
    #     fps=30
    # ):
    #     self.title = title
    #     self.resolution = resolution
    #     self.description = description
    #     self.language = language
    #     self.mode = mode
    #     self.cursor = cursor
    #     self.fps = fps