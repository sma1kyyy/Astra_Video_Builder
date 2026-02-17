from .vision_types import BBox

def apply_padding(bbox: BBox, padding: int) -> BBox:
    return BBox(
        x=bbox.x - padding,
        y=bbox.y - padding,
        width=bbox.width + padding * 2,
        height=bbox.height + padding * 2,
    )