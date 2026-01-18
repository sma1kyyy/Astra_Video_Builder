from src.schemas.ComponentObject import ComponentObject

class TextObject(ComponentObject):
    # кирилл: wait и duration в список разрешенных полей
    __static_attributes__ = [
        "text", 
        "start_x", 
        "start_y", 
        "size", 
        "font", 
        "wait", 
        "duration" 
    ]

    def __init__(
        self, 
        text: str, 
        start_x: int, 
        start_y: int, 
        size: int, 
        font: str = "arial", 
        wait: float = 0, 
        duration: float = 0
    ):
        self.text = text
        self.start_x = start_x
        self.start_y = start_y
        self.size = size
        self.font = font
        self.wait = wait
        self.duration = duration