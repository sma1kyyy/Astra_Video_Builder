from src.schemas.ComponentObject import ComponentObject

class AnnotationObject(ComponentObject):
    # кирилл: wait и duration и label и text (для квадратов)
    __static_attributes__ = [
        "type", 
        "transparency", 
        "start_x", 
        "start_y", 
        "end_x", 
        "end_y", 
        "wait", 
        "duration",
        "label",
        "text"
    ]

    def __init__(
        self, 
        type: str, 
        transparency: float, 
        start_x: int, 
        start_y: int, 
        end_x: int, 
        end_y: int, 
        wait: float = 0, 
        duration: float = 0,
        label: str = None,
        text: str = None
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