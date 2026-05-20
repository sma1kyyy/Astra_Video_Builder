from __future__ import annotations

import shutil

from fastapi import APIRouter

from web.backend.app.generator.config import get_settings

router = APIRouter(prefix="/api/generator", tags=["generator"])


def _ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


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
