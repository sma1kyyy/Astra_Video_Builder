from dataclasses import dataclass, field
from typing import List

from core.schemas.metadata_object import MetadataObject
from core.schemas.act_object import ActObject
from core.schemas.ComponentObject import ComponentObject


@dataclass
class VideoObject(ComponentObject):
    """корневой объект видео проекта"""

    metadata: MetadataObject
    acts: List[ActObject] = field(default_factory=list)

    # список полей для валидации в парсере
    __static_attributes__ = ["metadata", "acts"]

    def __repr__(self):
        return f"<Video: {self.metadata.title}| acts: {len(self.acts)}>"