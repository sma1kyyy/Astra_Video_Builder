# модель переведена на dataclass, чтобы избавиться от инитов
from dataclasses import dataclass, field, fields
from typing import List

from core.schemas.image_object import ImageObject
from core.schemas.audio_object import AudioObject
from core.schemas.text_object import TextObject
from core.schemas.action_object import ActionObject
from core.schemas.annotation_object import AnnotationObject
from core.schemas.ComponentObject import ComponentObject


@dataclass
class SceneObject(ComponentObject):
    path: str
    duration: float = 5.0
    name: str = "New Scene"
    tts: str = ""
    voice: str = "zahar"
    subtitles: bool = False
    subplace: str = "down"
    effect: str = "without"
    transition: str = "without"
    transpeed: float = 1.0

    # hard объекты (списки)
    images: List[ImageObject] = field(default_factory=list)
    audio: List[AudioObject] = field(default_factory=list)
    texts: List[TextObject] = field(default_factory=list)
    actions: List[ActionObject] = field(default_factory=list)
    annotations: List[AnnotationObject] = field(default_factory=list)

    @classmethod
    def get_static_attributes(cls) -> List[str]:
        """
        Автоматически возвращает список всех простых полей (атрибутов),
        которые не являются списками объектов.
        """
        excluded = ["images", "audio", "texts", "actions", "annotations"]
        return [f.name for f in fields(cls) if f.name not in excluded]

    def __post_init__(self):
        # валидация значений
        if self.duration < 0:
            self.duration = 1.0
        if self.transpeed < 0:
            self.transpeed = 0.5

    def __repr__(self):
        return f"<Scene '{self.name}' | dur: {self.duration}s>"