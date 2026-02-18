from dataclasses import dataclass

@dataclass
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self):
        return (
            self.x + self.width // 2,
            self.y + self.height // 2
        )