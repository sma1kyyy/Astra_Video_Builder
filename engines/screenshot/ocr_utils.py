import logging
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:
    import pytesseract
except Exception:  # pragma: no cover - безопасный fallback если зависимости не установлены
    pytesseract = None


def extract_roi(image: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Возвращает вырезанную область интереса и нормализованный bbox.
    Координаты автоматически нормализуются и ограничиваются размером кадра.
    """
    if image is None or image.size == 0:
        return np.zeros((1, 1, 3), dtype=np.uint8), (0, 0, 1, 1)

    height, width = image.shape[:2]

    left = max(0, min(int(x1), int(x2)))
    right = min(width, max(int(x1), int(x2)))
    top = max(0, min(int(y1), int(y2)))
    bottom = min(height, max(int(y1), int(y2)))

    # Гарантируем хотя бы 1 пиксель
    if right <= left:
        right = min(width, left + 1)
    if bottom <= top:
        bottom = min(height, top + 1)

    return image[top:bottom, left:right].copy(), (left, top, right, bottom)


def _preprocess_roi(roi: np.ndarray) -> np.ndarray:
    """
    Небольшая предобработка перед OCR: grayscale + autocontrast + upscale.
    """
    pil = Image.fromarray(roi)
    gray = ImageOps.grayscale(pil)
    boosted = ImageEnhance.Contrast(gray).enhance(1.8)

    # Легкий апскейл помогает Tesseract на мелком тексте.
    w, h = boosted.size
    upscaled = boosted.resize((max(1, w * 2), max(1, h * 2)), Image.Resampling.LANCZOS)

    return np.array(upscaled)


def run_ocr(roi: np.ndarray, lang: str = "rus+eng", min_conf: float = 0.0) -> Dict[str, float | str]:
    """
    Запускает OCR над ROI и возвращает итоговый текст и среднюю confidence.
    min_conf ожидается в диапазоне 0..1.
    """
    if pytesseract is None:
        logging.warning("pytesseract недоступен: OCR пропущен")
        return {"text": "", "confidence": 0.0}

    prepared = _preprocess_roi(roi)

    try:
        data = pytesseract.image_to_data(
            prepared,
            lang=lang,
            output_type=pytesseract.Output.DICT,
            config="--oem 3 --psm 6",
        )
    except Exception as error:
        logging.warning("Не удалось выполнить OCR: %s", error)
        return {"text": "", "confidence": 0.0}

    texts: list[str] = []
    confs: list[float] = []

    for i, raw_text in enumerate(data.get("text", [])):
        text = (raw_text or "").strip()
        raw_conf = data.get("conf", ["-1"])[i]

        try:
            conf = float(raw_conf)
        except (TypeError, ValueError):
            conf = -1.0

        if not text or conf < 0:
            continue

        conf01 = conf / 100.0
        if conf01 >= float(min_conf):
            texts.append(text)
            confs.append(conf01)

    if not texts:
        return {"text": "", "confidence": 0.0}

    avg_conf = sum(confs) / len(confs)
    return {"text": " ".join(texts), "confidence": round(avg_conf, 4)}
