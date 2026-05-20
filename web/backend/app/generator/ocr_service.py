from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import List, TypedDict

log = logging.getLogger(__name__)


class OCRItem(TypedDict):
    text: str
    bbox: List[int]
    conf: float


def _cache_key(image_path: Path) -> str:
    stat = image_path.stat()
    payload = f"{image_path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}".encode()
    return hashlib.sha256(payload).hexdigest()


def _cache_file(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def analyze_image(
    image_path: str | os.PathLike,
    cache_dir: str | os.PathLike,
    *,
    lang: str = "rus+eng",
    min_conf: float = 30.0,
) -> tuple[List[OCRItem], bool]:
    """OCR изображения с кэшированием по sha256(path+size+mtime).

    Возвращает (items, cached_flag).
    """
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"image not found: {image_path}")

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    key = _cache_key(image_path)
    cache_path = _cache_file(cache_dir, key)
    if cache_path.is_file():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8")), True
        except Exception:
            log.warning("OCR cache read failed for %s, regenerating", cache_path)

    items = _run_ocr(image_path, lang=lang, min_conf=min_conf)
    try:
        cache_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except Exception:
        log.exception("OCR cache write failed for %s", cache_path)
    return items, False


def _run_ocr(image_path: Path, *, lang: str, min_conf: float) -> List[OCRItem]:
    import pytesseract
    from PIL import Image

    image = Image.open(image_path)
    data = pytesseract.image_to_data(
        image,
        lang=lang,
        output_type=pytesseract.Output.DICT,
        config="--oem 3 --psm 6",
    )

    items: List[OCRItem] = []
    n = len(data.get("text", []))
    for i in range(n):
        raw_text = (data["text"][i] or "").strip()
        if not raw_text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < min_conf:
            continue
        x, y, w, h = int(data["left"][i]), int(data["top"][i]), int(data["width"][i]), int(data["height"][i])
        items.append({
            "text": raw_text,
            "bbox": [x, y, x + w, y + h],
            "conf": round(conf, 2),
        })
    return items
