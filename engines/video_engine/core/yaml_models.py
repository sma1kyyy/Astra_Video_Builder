from dataclasses import dataclass

@dataclass
class HighlightConfig:
    target_text: str
    padding: int = 0
    darken_background: bool = True