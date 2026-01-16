from src.schemas.addable_object import AddableObject

class AudioObject(AddableObject):
    def __init__(
        self,
        path: str,
        _from,
        duration,
        wait=0,
    ):
        super().__init__(wait, duration)
        self.path = path
        self._from = _from