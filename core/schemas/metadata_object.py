from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict
from typing import Optional, Literal

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
    language: Literal["ru", "en"] = Field(
        default="ru",
        description="Язык TTS."
    )
    mode: Literal["live", "screenshot"] = Field(
        default="live",
        description="Режим создания видео."
    )
    browser: Literal["chrome", "firefox"] = Field(
        default="chrome",
        description="Браузер для Live Recording режима."
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
    save_files: bool = Field(
        default=False,
        description=(
            "Сохранять промежуточные файлы (TTS-аудио, исходную запись и т. д.) "
            "после рендера. По умолчанию — удалять."
        ),
    )