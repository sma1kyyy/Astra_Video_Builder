from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict
from typing import List

from core.schemas.scene_object import SceneObject
from core.schemas.ComponentObject import ComponentObject


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class ActObject(ComponentObject):
    """шаблон акта для логической группировки сцен"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Название акта",
        pattern=r'^[А-Яа-яA-Za-z0-9\s\-_]+$'
    )
    
    # Поле со значением по умолчанию
    scenes: List[SceneObject] = Field(
        ...,
        description="Список сцен в акте"
    )

    # список полей для валидации в парсере
    __static_attributes__ = ["name", "scenes"]

    def __repr__(self):
        return f"<Act: {self.name} | scenes: {len(self.scenes)}>"
