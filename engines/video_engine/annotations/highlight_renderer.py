import numpy as np
from moviepy.editor import ColorClip, CompositeVideoClip, VideoClip
from .animation_utils import pulse_color


def _create_darken_layer(size, bbox, opacity=0.6):
    w, h = size

    dark = ColorClip(size, color=(0, 0, 0)).set_opacity(opacity)

    mask = np.ones((h, w), dtype=float)

    x, y = bbox.x, bbox.y
    bw, bh = bbox.width, bbox.height

    mask[y:y+bh, x:x+bw] = 0

    dark = dark.set_mask(
        ColorClip(size, color=1)
        .set_opacity(1)
        .set_make_frame(lambda t: mask)
    )

    return dark


def _create_border_clip(bbox, duration, animation="pulse"):
    def make_frame(t):
        img = np.zeros((bbox.height, bbox.width, 3), dtype=np.uint8)
        thickness = 4

        base_color = (255, 200, 0)

        if animation == "pulse":
            color = pulse_color(base_color, t)
        else:
            color = base_color

        img[:thickness, :] = color
        img[-thickness:, :] = color
        img[:, :thickness] = color
        img[:, -thickness:] = color

        return img

    return (
        VideoClip(make_frame, duration=duration)
        .set_position((bbox.x, bbox.y))
    )


def render_highlight(base_clip, bbox, duration=2, darken=True, animation="pulse"):
    layers = [base_clip]

    if darken:
        dark_layer = _create_darken_layer(base_clip.size, bbox)
        layers.append(dark_layer)

    border = _create_border_clip(bbox, duration, animation)
    layers.append(border)

    return CompositeVideoClip(layers)