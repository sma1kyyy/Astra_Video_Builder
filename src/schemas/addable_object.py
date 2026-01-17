from src.schemas.ComponentObject import ComponentObject

class AddableObject(ComponentObject):
    def __init__(self, wait=0, duration=0):
        self.wait = wait
        self.duration = duration