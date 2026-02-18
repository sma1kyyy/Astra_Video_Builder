from core.schemas.addable_object import AddableObject

class ImageObject(AddableObject):
    def __init__(
        self,
        path: str,
        start_x: int,
        start_y: int,
        resolution: str,
        wait=0,
        duration=None
    ):
        super().__init__(wait, duration)
        self.path = path
        self.start_x = start_x
        self.start_y = start_y
        self.resolution = resolution