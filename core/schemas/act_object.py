from dataclasses import dataclass, field
from typing import List

from core.schemas.scene_object import SceneObject
from core.schemas.ComponentObject import ComponentObject


@dataclass
class ActObject(ComponentObject):
    """объект акта для логической группировки сцен"""

    name: str = "new act"
    scenes: List[SceneObject] = field(default_factory=list)

    # список полей для валидации в парсере
    __static_attributes__ = ["name", "scenes"]

    def __repr__(self):
        return f"<Act: {self.name} | scenes: {len(self.scenes)}>"
