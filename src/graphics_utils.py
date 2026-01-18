# Модуль для рисования аннотаций 
# Логика рисования стрелок
# Библиотека Pillow для рисования прозрачных слоев, а после накладка их в видео
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import math

def create_annotation_image(
    width,
    height,
    annot_type,
    start,
    end,
    color=(255, 80, 80),
    thickness=None
):
    # динамическая толщина под разрешение
    if thickness is None:
        thickness = max(6, width // 300)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x1, y1 = start
    x2, y2 = end

    def draw_shadow(shape_fn, offset=4, blur=8):
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shape_fn(shadow_draw, (0, 0, 0, 180))
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
        img.alpha_composite(shadow, (offset, offset))

    if annot_type == "square":
        padding = 8
        radius = thickness * 2

        def square_shape(d, col):
            d.rounded_rectangle(
                [x1-padding, y1-padding, x2+padding, y2+padding],
                radius=radius,
                outline=col,
                width=thickness
            )

        draw_shadow(square_shape)
        square_shape(draw, color + (255,))

    elif annot_type == "arrow":
        # линия стрелки
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_len = thickness * 4

        # наконечник
        left = (
            x2 - arrow_len * math.cos(angle - math.pi / 6),
            y2 - arrow_len * math.sin(angle - math.pi / 6),
        )
        right = (
            x2 - arrow_len * math.cos(angle + math.pi / 6),
            y2 - arrow_len * math.sin(angle + math.pi / 6),
        )

        def arrow_shape(d, col):
            d.line([x1, y1, x2, y2], fill=col, width=thickness)
            d.polygon([x2, y2, left, right], fill=col)

        draw_shadow(arrow_shape)
        arrow_shape(draw, color + (255,))

    return np.array(img)

def create_focus_mask(
    width,
    height,
    x1,
    y1,
    x2,
    y2,
    opacity=180,
    radius=30
):
    # auto-focus маска: затемняет весь экран, оставляя прозрачное окно фокуса
    img = Image.new("RGBA", (width, height), (0, 0, 0, opacity))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=radius,
        fill=(0, 0, 0, 0)
    )

    return np.array(img)


def create_text_bg(
    width,
    height,
    text_x,
    text_y,
    text_w,
    text_h,
    padding=20,
    radius=18,
    opacity=180
):
    # подложка под текст (onboarding стиль)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    rect = [
        text_x - padding,
        text_y - padding,
        text_x + text_w + padding,
        text_y + text_h + padding
    ]

    draw.rounded_rectangle(
        rect,
        radius=radius,
        fill=(0, 0, 0, opacity)
    )

    img = img.filter(ImageFilter.GaussianBlur(2))
    return np.array(img)

def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)

def ease_out(t: float) -> float:
    return 1 - (1 - t) * (1 - t)

def ease_in(t: float) -> float:
    return t * t

def normalize_rect(x1, y1, x2, y2):
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
