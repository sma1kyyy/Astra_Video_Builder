from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict, model_validator
from dataclasses import fields
from typing import List, Optional, Literal

from core.schemas.metadata_object import MetadataObject
from core.schemas.act_object import ActObject
from core.schemas.ComponentObject import ComponentObject


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class VideoObject(ComponentObject):
    """корневой объект видео проекта"""

    metadata: MetadataObject = Field(
        ...,
        description="Объект metadata"
    )
    acts: List[ActObject] = Field(
        ...,
        description="Список с актами"
    )

    # список полей для валидации в парсере
    __static_attributes__ = ["metadata", "acts"]

    def __repr__(self):
        return f"<Video: {self.metadata.title}| acts: {len(self.acts)}>"