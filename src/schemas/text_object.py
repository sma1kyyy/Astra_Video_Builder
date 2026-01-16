from src.schemas.addable_object import AddableObject

class TextObject(AddableObject):
    def __init__(
        self,
        text: str,
        start_x: int,
        start_y: int,
        size: int,
        font="arial",
        wait=0,
        duration=None
    ):
        super().__init__(wait, duration)
        self.text = text
        self.start_x = start_x
        self.start_y = start_y
        self.size = size
        self.font = font