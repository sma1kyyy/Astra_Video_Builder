import numpy as np
from moviepy.editor import VideoClip


def render_arrow(base_clip, bbox, duration=2):
    center_x, center_y = bbox.center

    arrow_size = 80

    def make_frame(t):
        img = np.zeros((arrow_size, arrow_size, 3), dtype=np.uint8)

        color = (255, 0, 0)

        for i in range(arrow_size):
            img[i, arrow_size//2 - 2:arrow_size//2 + 2] = color

        for i in range(arrow_size//2):
            img[arrow_size//2 - i, arrow_size//2 - i] = color
            img[arrow_size//2 - i, arrow_size//2 + i] = color

        return img

    arrow_clip = VideoClip(make_frame, duration=duration)

    return arrow_clip.set_position(
        (center_x - arrow_size//2, center_y - arrow_size - 10)
    )