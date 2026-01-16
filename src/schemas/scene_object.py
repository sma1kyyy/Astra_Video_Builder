from typing import List

# object imports
from src.schemas.image_object import ImageObject
from src.schemas.audio_object import AudioObject
from src.schemas.text_object import TextObject
from src.schemas.action_object import ActionObject

class SceneObject:
    def __init__(
        self,
        duration: int,
        name = "",
        tts = "",
        voice = "standart",
        subtitles = False,
        subplace = "down",
        effect = "without",
        images: List[ImageObject] = [],
        audio: List[AudioObject] = [],
        texts: List[TextObject] = [],
        actions: List[ActionObject] = []
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