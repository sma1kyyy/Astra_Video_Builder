from src.schemas.ComponentObject import ComponentObject
from src.schemas.validation_object import Valid

class ActionObject(ComponentObject):
    def __init__(
        self,
        type: str,
        url = None,
        selector = None,
        text = None,
        duration = None,
        point = None,
        wait = 0
    ):
        self.type = type
        self.url = url
        self.selector = selector
        self.text = text
        self.duration = duration
        self.point = point
        self.wait = wait