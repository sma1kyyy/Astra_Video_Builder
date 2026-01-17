from src.schemas.ComponentObject import ComponentObject

class AnnotationObject(ComponentObject):
    def __init__(
            self,
            type: str,
            transparency: int,
            start_x: int,
            start_y: int,
            end_x,
            end_y,
            wait = 0,
            duration = 0,
            label = "",
            text = ""
    ):
        self.type = type
        self.transparency = transparency
        self.start_x = start_x
        self.start_y = start_y
        self.end_x = end_x
        self.end_y = end_y
        self.wait = wait
        self.duration = duration
        self.label = label
        self.text = text