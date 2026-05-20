from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from web.backend.app.generator.config import get_settings
from web.backend.app.generator.ocr_service import analyze_image

router = APIRouter(prefix="/api/generator", tags=["generator"])


def _ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def _work_dir() -> Path:
    from web.backend.app.main import WORK_DIR
    return WORK_DIR


def _assets_dir() -> Path:
    from web.backend.app.main import ASSETS_DIR
    return ASSETS_DIR


def _safe_asset_path(filename: str) -> Path:
    base = os.path.basename(filename)
    cleaned = "".join(c for c in base if c.isalnum() or c in "._-")
    if not cleaned:
        raise HTTPException(status_code=400, detail="invalid filename")
    return _assets_dir() / cleaned


class AnalyzeAssetRequest(BaseModel):
    filename: str = Field(..., min_length=1)


@router.get("/status")
def status() -> dict:
    settings = get_settings()
    return {
        "llm_configured": settings.is_configured,
        "llm_model": settings.llm_model if settings.is_configured else None,
        "vision_enabled": settings.llm_vision_enabled,
        "ocr_available": _ocr_available(),
        "rate_limit": settings.generator_rate_limit,
    }


@router.post("/analyze-asset")
def analyze_asset(body: AnalyzeAssetRequest) -> dict:
    if not _ocr_available():
        raise HTTPException(status_code=503, detail="OCR is not available on this server")

    asset_path = _safe_asset_path(body.filename)
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail=f"asset not found: {body.filename}")

    cache_dir = _work_dir() / "ocr_cache"
    try:
        items, cached = analyze_image(asset_path, cache_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}")

    return {
        "filename": asset_path.name,
        "cached": cached,
        "items_count": len(items),
        "items": items,
    }

