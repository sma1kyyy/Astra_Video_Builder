import numpy as np
from moviepy.editor import ColorClip, CompositeVideoClip


def render_spotlight(base_clip, bbox, duration=2, opacity=0.7):
    w, h = base_clip.size

    dark = ColorClip((w, h), color=(0, 0, 0)).set_opacity(opacity)

    mask = np.ones((h, w), dtype=float)

    cx, cy = bbox.center
    radius = max(bbox.width, bbox.height)

    Y, X = np.ogrid[:h, :w]
    dist = (X - cx) ** 2 + (Y - cy) ** 2

    mask[dist <= radius**2] = 0

    dark = dark.set_mask(
        ColorClip((w, h), color=1)
        .set_opacity(1)
        .set_make_frame(lambda t: mask)
    )

    return CompositeVideoClip([base_clip, dark])