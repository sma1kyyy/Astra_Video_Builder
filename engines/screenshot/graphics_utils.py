import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def create_annotation_image(
    width,
    height,
    annot_type,
    start,
    end,
    color=(255, 50, 50),
    thickness=None,
):
    """
    Создает слой аннотации с использованием Supersampling (2x) для идеального сглаживания.
    """
    # Гарантируем целые размеры
    width = int(round(width))
    height = int(round(height))

    scale = 2  # Рисуем в 2 раза крупнее для антиалиасинга
    w, h = width * scale, height * scale

    # Координаты тоже приводим к int
    x1 = int(round(start[0] * scale))
    y1 = int(round(start[1] * scale))
    x2 = int(round(end[0] * scale))
    y2 = int(round(end[1] * scale))

    if thickness is None:
        thickness = max(4, width // 200) * scale
    else:
        thickness = int(round(thickness * scale))

    # Создаем холст аннотации
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def draw_shape(d: ImageDraw.ImageDraw, col, width_val):
        width_val = int(round(width_val))

        if annot_type == "square":
            padding = int(10 * scale)
            d.rounded_rectangle(
                [x1 - padding, y1 - padding, x2 + padding, y2 + padding],
                radius=int(15 * scale),
                outline=col,
                width=width_val,
            )
        elif annot_type == "arrow":
            angle = math.atan2(y2 - y1, x2 - x1)
            arrow_len = width_val * 4

            left = (
                x2 - arrow_len * math.cos(angle - math.pi / 7),
                y2 - arrow_len * math.sin(angle - math.pi / 7),
            )
            right = (
                x2 - arrow_len * math.cos(angle + math.pi / 7),
                y2 - arrow_len * math.sin(angle + math.pi / 7),
            )

            # Линия
            d.line([x1, y1, x2, y2], fill=col, width=width_val)
            # Стрелка (координаты можно оставить float — PIL их понимает)
            d.polygon([ (x2, y2), left, right ], fill=col)

    # Эффект Glow (мягкое свечение под основной фигурой)
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    draw_shape(glow_draw, color + (80,), thickness + 4 * scale)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(int(5 * scale)))
    img.alpha_composite(glow_layer)

    # Основная фигура
    draw_shape(draw, color + (255,), thickness)

    # Возврат к исходному размеру с качественной фильтрацией
    img = img.resize((width, height), resample=Image.LANCZOS)
    return np.array(img)


def create_focus_mask(width, height, x1, y1, x2, y2, opacity=170, radius=45):
    """
    Создает мягкую маску фокуса (Vignette). Затемняет всё, кроме целевой области.
    """
    width = int(round(width))
    height = int(round(height))
    x1 = int(round(x1))
    y1 = int(round(y1))
    x2 = int(round(x2))
    y2 = int(round(y2))
    opacity = int(round(opacity))
    radius = int(round(radius))

    mask = Image.new("L", (width, height), opacity)
    draw = ImageDraw.Draw(mask)

    # "Вырезаем" окно
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=0)

    # Размываем края маски для кинематографичного эффекта
    mask = mask.filter(ImageFilter.GaussianBlur(12))

    # Накладываем на черный слой
    black_layer = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    final_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    final_img = Image.composite(final_img, black_layer, mask)

    return np.array(final_img)


def create_text_bg(width, height, text_x, text_y, text_w, text_h, padding=25):
    """
    Создает элегантную подложку под текст в стиле Onboarding.
    """
    width = int(round(width))
    height = int(round(height))
    text_x = int(round(text_x))
    text_y = int(round(text_y))
    text_w = int(round(text_w))
    text_h = int(round(text_h))
    padding = int(round(padding))

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    rect = [
        text_x - padding,
        text_y - padding,
        text_x + text_w + padding,
        text_y + text_h + padding,
    ]
    draw.rounded_rectangle(rect, radius=15, fill=(15, 15, 15, 190))

    img = img.filter(ImageFilter.GaussianBlur(1))
    return np.array(img)


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)
