# basic lib imports
from typing import List

# service imports
from src.schemas.metadata_object import MetadataObject
from src.schemas.scene_object import SceneObject

class VideoObject:
    def __init__(self, metadata: MetadataObject, scenes: List[SceneObject]):
        self.metadata = metadata
        self.scenes = scenes