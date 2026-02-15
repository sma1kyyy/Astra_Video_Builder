from typing import List

# schemas imports
from src.schemas.image_object import ImageObject
from src.schemas.audio_object import AudioObject
from src.schemas.text_object import TextObject
from src.schemas.action_object import ActionObject
from src.schemas.annotation_object import AnnotationObject
from src.schemas.ComponentObject import ComponentObject


class SceneObject(ComponentObject):
    def __init__(
        self,
        duration: int,
        name = "",
        tts = "",
        voice = "jane",
        subtitles = False,
        subplace = "down",
        effect = "without",
        transition = "without",
        transpeed = 0,
        path = "",
        images: List[ImageObject] = [],
        audio: List[AudioObject] = [],
        texts: List[TextObject] = [],
        actions: List[ActionObject] = [],
        annotations: List[AnnotationObject] = [],
    ):
        self.duration = duration
        self.name = name
        self.tts = tts
        self.voice = voice
        self.subtitles = subtitles
        self.subplace = subplace
        self.effect = effect
        self.images = images
        self.audio = audio
        self.texts = texts
        self.actions = actions
        self.annotations = annotations
        self.transition = transition
        self.transpeed = transpeed
        self.path = path

    def __repr__(self):
        extra_info = "\n"
        if self.images:
            extra_info += f"<Images: {[image for image in self.images]}>\n"
        if self.audio:
            extra_info += f"<Audio: {[audio for audio in self.audio]}>\n"
        if self.texts:
            extra_info += f"<Texts: {[text for text in self.texts]}>\n"
        if self.actions:
            extra_info += f"<Actions: {[action for action in self.actions]}>\n"
        if self.annotations:
            extra_info += f"<Annotations: {[annotation for annotation in self.annotations]}>"
        return f"""
        <SceneObject: {self.__dict__}>
        """ + extra_info