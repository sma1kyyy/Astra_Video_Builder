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
        # валидация базовых типов
        assert isinstance(duration, int) and duration > 0, "Неверное число в duration"
        assert isinstance(point, int) and point > 0, "Неверное число в point"
        assert isinstance(wait, int) and wait > 0, "Неверное число в wait"

        # валидация особых типов
        assert Valid.validate_selector(selector), "Неверный формат selector"
        assert Valid.validate_url(url), "Неверный формат URL"

        self.type = type
        self.url = url
        self.selector = selector
        self.text = text
        self.duration = duration
        self.point = point
        self.wait = wait