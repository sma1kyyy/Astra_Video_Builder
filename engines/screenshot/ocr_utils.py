import logging
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:
    import pytesseract
except Exception:  # pragma: no cover - безопасный fallback если зависимости не установлены
    pytesseract = None

_ocr_warned_once = False
_ocr_available_cache: bool | None = None


def _warn_ocr_unavailable(reason: str):
    global _ocr_warned_once
    if not _ocr_warned_once:
        logging.warning("OCR недоступен: %s", reason)
        _ocr_warned_once = True


def _mark_ocr_unavailable(reason: str):
    global _ocr_available_cache
    _ocr_available_cache = False
    _warn_ocr_unavailable(reason)


def is_ocr_available() -> bool:
    global _ocr_available_cache

    if _ocr_available_cache is not None:
        return _ocr_available_cache

    if pytesseract is None:
        _mark_ocr_unavailable("pytesseract не импортирован")
        return False

    try:
        _ = pytesseract.get_tesseract_version()
        _ocr_available_cache = True
        return True
    except Exception as error:
        _mark_ocr_unavailable(f"tesseract не установлен или не в PATH ({error})")
        return False


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

def _run_tesseract_data(image: np.ndarray, lang: str, psm: int) -> Dict[str, List]:
    return pytesseract.image_to_data(
        image,
        lang=lang,
        output_type=pytesseract.Output.DICT,
        config=f"--oem 3 --psm {psm}",
    )

def _is_missing_tesseract_error(error: Exception) -> bool:
    msg = str(error).lower()
    return "tesseract is not installed" in msg or "not in your path" in msg

def detect_text_candidates(image: np.ndarray, lang: str = "rus+eng", min_conf: float = 0.25) -> List[Dict]:
    if not is_ocr_available() or image is None or image.size == 0:
        return []

    prepared = _preprocess_roi(image)
    candidates: List[Dict] = []

    for psm in (6, 11):
        try:
            data = _run_tesseract_data(prepared, lang, psm)
        except Exception as error:
            if _is_missing_tesseract_error(error):
                _mark_ocr_unavailable(str(error))
                return []
            logging.warning("не удалось выполнить OCR psm=%s: %s", psm, error)
            continue

        scale_x = image.shape[1] / prepared.shape[1]
        scale_y = image.shape[0] / prepared.shape[0]

        for i, raw_text in enumerate(data.get("text", [])):
            text = (raw_text or "").strip()
            if not text:
                continue

            raw_conf = data.get("conf", ["-1"])[i]
            try:
                conf = max(0.0, float(raw_conf) / 100.0)
            except (TypeError, ValueError):
                conf = 0.0

            if conf < min_conf:
                continue

            left = int(float(data.get("left", [0])[i]) * scale_x)
            top = int(float(data.get("top", [0])[i]) * scale_y)
            width = int(float(data.get("width", [1])[i]) * scale_x)
            height = int(float(data.get("height", [1])[i]) * scale_y)

            right = left + max(1, width)
            bottom = top + max(1, height)
            candidates.append({"text": text, "confidence": conf, "bbox": (left, top, right, bottom)})

    return candidates


def run_ocr(roi: np.ndarray, lang: str = "rus+eng", min_conf: float = 0.0) -> Dict[str, float | str]:
    if not is_ocr_available():
        return {"text": "", "confidence": 0.0}

    prepared = _preprocess_roi(roi)
    candidates: List[Tuple[str, float]] = []

    for psm in (6, 11):
        try:
            data = _run_tesseract_data(prepared, lang, psm)
        except Exception as error:
            if _is_missing_tesseract_error(error):
                _mark_ocr_unavailable(str(error))
                return {"text": "", "confidence": 0.0}
            logging.warning("не удалось выполнить OCR: %s", error)


    # try:
    #     data = pytesseract.image_to_data(
    #         prepared,
    #         lang=lang,
    #         output_type=pytesseract.Output.DICT,
    #         config="--oem 3 --psm 6",
    #     )
    # except Exception as error:
    #     logging.warning("Не удалось выполнить OCR: %s", error)
    #     return {"text": "", "confidence": 0.0}

    # texts: list[str] = []
    # confs: list[float] = []
            continue

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
                candidates.append((text, conf01))


        # conf01 = conf / 100.0
        # if conf01 >= float(min_conf):
        #     texts.append(text)
        #     confs.append(conf01)


    # if not texts:
    if not candidates:
        return {"text": "", "confidence": 0.0}

    # avg_conf = sum(confs) / len(confs)
    # return {"text": " ".join(texts), "confidence": round(avg_conf, 4)}
    text_out = " ".join([t for t, _ in candidates]).strip()
    avg_conf = float(sum(c for _, c in candidates) / len(candidates))
    return {"text": text_out, "confidence": avg_conf}


