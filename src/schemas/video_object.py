# basic lib imports
from typing import List

# schemas imports
from src.schemas.metadata_object import MetadataObject
from src.schemas.scene_object import SceneObject
from src.schemas.ComponentObject import ComponentObject

class VideoObject(ComponentObject):
    def __init__(self, metadata: MetadataObject, scenes: List[SceneObject]):
        self.metadata = metadata
        self.scenes = scenes

    def __repr__(self):
        extra_info = ""
        if self.scenes:
            extra_info += f" --- Scenes: {[scene for scene in self.scenes]}>"
        return f"<VideoObject --- Metadata: {self.metadata}" + extra_info