# модель переведена на dataclass, чтобы избавиться от инитов
from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict, model_validator
from dataclasses import fields
from typing import List, Optional, Literal

from core.schemas.image_object import ImageObject
from core.schemas.audio_object import AudioObject
from core.schemas.text_object import TextObject
from core.schemas.action_object import ActionObject
from core.schemas.annotation_object import AnnotationObject
from core.schemas.ComponentObject import ComponentObject

@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class SceneObject(ComponentObject):
    path: Optional[str] = Field(
        default=None,
        description="Путь до скриншота."
    )
    duration: Optional[float] = Field(
        default=1.0,
        description="Минимальная длительность сцены."
    )
    name: Optional[str] = Field(
        default="new scene",
        description="Название сцены для логов."
    )
    tts: Optional[str] = Field(
        default="",
        description="Текст TTS (если нужен)."
    )
    voice: Literal["jane", "zahar"] = Field(
        default="jane",
        description="Голос TTS."
    )
    subtitles: Optional[bool] = Field(
        default=False,
        description="Включить или отключить субтитры."
    )
    subplace: Literal["up", "down", "center"] = Field(
        default="down",
        description="Расположение субтитров."
    )
    effect: Literal["without", "black_white"] = Field(
        default="without",
        description="Эффект сцены."
    )
    transition: Literal["without", "slideRight", "slideLeft", "slideUp", "slideDown", "blackout"] = Field(
        default="without",
        description="Переход на следующую аннотацию."
    )
    transpeed: Optional[float] = Field(
        default=1.0,
        description="Длительность перехода."
    )

    # hard объекты (списки)
    images: Optional[List[ImageObject]] = Field(
        default_factory=list,
        description="Список с изображениями."
    )
    audio: Optional[List[AudioObject]] = Field(
        default_factory=list,
        description="Список с объектами аудио."
    )
    texts: Optional[List[TextObject]] = Field(
        default_factory=list,
        description="Список с объектами текста."
    )
    actions: Optional[List[ActionObject]] = Field(
        default_factory=list,
        description="Список с действиями."
    )
    annotations: Optional[List[AnnotationObject]] = Field(
        default_factory=list,
        description="Список с аннотациями."
    )

    @classmethod
    def get_static_attributes(cls) -> List[str]:
        """
        Автоматически возвращает список всех простых полей (атрибутов),
        которые не являются списками объектов.
        """
        excluded = ["images", "audio", "texts", "actions", "annotations"]
        return [f.name for f in fields(cls) if f.name not in excluded]

    @model_validator(mode="after")
    def post_init(self) -> "SceneObject":
        # валидация значений
        if self.duration < 0:
            self.duration = 1.0
        if self.transpeed < 0:
            self.transpeed = 0.5

        if self.effect == "without":
            self.effect = None

        assert len(self.annotations) == 0 and not self.path, "There must be path for screenshot or list with annotations."
        
        return self

    def __repr__(self):
        return f"<Scene '{self.name}' | dur: {self.duration}s>"

# @dataclass
# class SceneObject(ComponentObject):
#     path: str
#     duration: float = 5.0
#     name: str = "New Scene"
#     tts: str = ""
#     voice: str = "zahar"
#     subtitles: bool = False
#     subplace: str = "down"
#     effect: str = "without"
#     transition: str = "without"
#     transpeed: float = 1.0

#     # hard объекты (списки)
#     images: List[ImageObject] = field(default_factory=list)
#     audio: List[AudioObject] = field(default_factory=list)
#     texts: List[TextObject] = field(default_factory=list)
#     actions: List[ActionObject] = field(default_factory=list)
#     annotations: List[AnnotationObject] = field(default_factory=list)

#     @classmethod
#     def get_static_attributes(cls) -> List[str]:
#         """
#         Автоматически возвращает список всех простых полей (атрибутов),
#         которые не являются списками объектов.
#         """
#         excluded = ["images", "audio", "texts", "actions", "annotations"]
#         return [f.name for f in fields(cls) if f.name not in excluded]

#     def __post_init__(self):
#         # валидация значений
#         if self.duration < 0:
#             self.duration = 1.0
#         if self.transpeed < 0:
#             self.transpeed = 0.5

#     def __repr__(self):
#         return f"<Scene '{self.name}' | dur: {self.duration}s>"