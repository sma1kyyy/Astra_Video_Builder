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
    Создает слой аннотации с использованием Supersampling (2x) для сглаживания

    Поддерживаемые типы:
      square  — прямоугольник с скруглёнными углами
      line    — прямая линия
      arrow   — стрелка в одну сторону (от start к end)
      darrow  — двунаправленная стрелка (от start к end и обратно)
    """
    width = int(round(width))
    height = int(round(height))

    scale = 2
    w, h = width * scale, height * scale

    x1 = int(round(start[0] * scale))
    y1 = int(round(start[1] * scale))
    x2 = int(round(end[0] * scale))
    y2 = int(round(end[1] * scale))

    if thickness is None:
        thickness = max(4, width // 200) * scale
    else:
        thickness = int(round(thickness * scale))

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def _arrowhead(d, tip_x, tip_y, angle, col, w_val):
        """Рисует наконечник стрелки в точке (tip_x, tip_y) по направлению angle"""
        arrow_len = w_val * 4
        left = (
            tip_x - arrow_len * math.cos(angle - math.pi / 7),
            tip_y - arrow_len * math.sin(angle - math.pi / 7),
        )
        right = (
            tip_x - arrow_len * math.cos(angle + math.pi / 7),
            tip_y - arrow_len * math.sin(angle + math.pi / 7),
        )
        d.polygon([(tip_x, tip_y), left, right], fill=col)

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
        elif annot_type == "line":
            d.line([x1, y1, x2, y2], fill=col, width=width_val)
        elif annot_type == "arrow":
            angle = math.atan2(y2 - y1, x2 - x1)
            d.line([x1, y1, x2, y2], fill=col, width=width_val)
            _arrowhead(d, x2, y2, angle, col, width_val)
        elif annot_type == "darrow":
            # Оставлен только правильный, лаконичный вариант
            angle_fwd = math.atan2(y2 - y1, x2 - x1)
            angle_bwd = math.atan2(y1 - y2, x1 - x2)
            d.line([x1, y1, x2, y2], fill=col, width=width_val)
            _arrowhead(d, x2, y2, angle_fwd, col, width_val)
            _arrowhead(d, x1, y1, angle_bwd, col, width_val)

    # Glow
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    draw_shape(glow_draw, color + (80,), thickness + 4 * scale)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(int(5 * scale)))
    img.alpha_composite(glow_layer)

    # Основная фигура
    draw_shape(draw, color + (255,), thickness)

    img = img.resize((width, height), resample=Image.LANCZOS)
    return np.array(img)


def create_focus_mask(width, height, x1, y1, x2, y2, opacity=170, radius=45):
    """Создает мягкую маску фокуса (Vignette)"""
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
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(12))

    black_layer = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    final_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    final_img = Image.composite(final_img, black_layer, mask)
    return np.array(final_img)


def create_text_bg(width, height, text_x, text_y, text_w, text_h, padding=25):
    """Создает подложку под текст"""
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


# slide transition helpers

def make_slide_transition_frame(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    progress: float,
    direction: str,
) -> np.ndarray:
    """
    Создаёт один кадр slide-перехода между двумя кадрами

    frame_a  — уходящий кадр (shape H×W×3, uint8)
    frame_b  — входящий кадр (shape H×W×3, uint8)
    progress — 0.0 … 1.0 (насколько завершён переход)
    direction — 'slideRight' | 'slideLeft' | 'slideUp' | 'slideDown'

    Возвращает смешанный кадр той же формы
    """
    h, w = frame_a.shape[:2]
    t = float(np.clip(progress, 0.0, 1.0))
    t = ease_in_out(t)

    result = np.zeros_like(frame_a)

    if direction == "slideRight":
        offset = int(round(w * t))
        if offset < w: 
            result[:, offset:] = frame_a[:, :w - offset]
        if offset > 0: 
            result[:, :offset] = frame_b[:, w - offset:]

    elif direction == "slideLeft":
        offset = int(round(w * t))
        if offset < w: 
            result[:, :w - offset] = frame_a[:, offset:]
        if offset > 0: 
            result[:, w - offset:] = frame_b[:, :offset]

    elif direction == "slideDown":
        offset = int(round(h * t))
        if offset < h: 
            result[offset:, :] = frame_a[:h - offset, :]
        if offset > 0: 
            result[:offset, :] = frame_b[h - offset:, :]

    elif direction == "slideUp":
        offset = int(round(h * t))
        if offset < h: 
            result[:h - offset, :] = frame_a[offset:, :]
        if offset > 0: 
            result[h - offset:, :] = frame_b[:offset, :]

    else:
        result = frame_a.copy()

    return result