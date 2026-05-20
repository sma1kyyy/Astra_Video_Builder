from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from web.backend.app.generator.agent_loop import run_agent_loop
from web.backend.app.generator.config import get_settings
from web.backend.app.generator.llm_client import LLMClient, LLMNotConfiguredError
from web.backend.app.generator.ocr_service import analyze_image
from web.backend.app.generator.prompts import build_screenshot_prompt

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generator", tags=["generator"])
limiter = Limiter(key_func=get_remote_address, default_limits=[])


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


class GenerateRequest(BaseModel):
    mode: Literal["live", "screenshot"]
    task: str = Field(..., min_length=1, max_length=5000)
    start_url: str | None = None
    browser: Literal["chrome", "firefox"] = "chrome"
    asset_filenames: list[str] = Field(default_factory=list)
    asset_descriptions: dict[str, str] | None = None
    voice: Literal["jane", "zahar"] = "jane"
    language: Literal["ru", "en"] = "ru"
    resolution: str = "1920x1080"
    fps: int = Field(default=24, ge=1, le=120)
    max_iterations: int | None = Field(default=None, ge=1, le=50)
    total_timeout: float | None = Field(default=None, gt=0, le=600)


class GenerateResponse(BaseModel):
    yaml_script: str
    mode: str
    valid: bool
    parse_error: str | None = None
    iterations: int | None = None
    exploration_incomplete: bool | None = None
    verification_passed: bool | None = None
    verification_attempts: int | None = None
    verification_issues: list[str] | None = None
    timed_out: bool | None = None
    hit_iteration_limit: bool | None = None
    notes: str | None = None
    ocr_used: bool | None = None
    self_correction_used: bool | None = None


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


def _validate_yaml(yaml_text: str) -> tuple[bool, str | None]:
    from core.parser import parse

    if not yaml_text or not yaml_text.strip():
        return False, "empty YAML"
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
        tmp.write(yaml_text)
        tmp_path = tmp.name
    try:
        parse(tmp_path)
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _preflight_live(req: GenerateRequest) -> None:
    if not req.start_url or not req.start_url.strip():
        raise HTTPException(status_code=400, detail="start_url is required for live mode")
    url = req.start_url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="start_url must start with http:// or https://")


def _preflight_screenshot(req: GenerateRequest) -> list[Path]:
    if not req.asset_filenames:
        raise HTTPException(status_code=400, detail="asset_filenames is required for screenshot mode")
    resolved: list[Path] = []
    for name in req.asset_filenames:
        path = _safe_asset_path(name)
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"asset not found: {name}")
        resolved.append(path)
    return resolved


async def _generate_live(req: GenerateRequest, client: LLMClient) -> GenerateResponse:
    kwargs: dict = {}
    if req.max_iterations is not None:
        kwargs["max_iterations"] = req.max_iterations
    if req.total_timeout is not None:
        kwargs["total_timeout"] = req.total_timeout

    result = await run_agent_loop(
        task_description=req.task,
        start_url=req.start_url,
        llm_client=client,
        voice=req.voice,
        browser=req.browser,
        language=req.language,
        resolution=req.resolution,
        fps=req.fps,
        **kwargs,
    )

    valid, parse_error = _validate_yaml(result.yaml_script)

    return GenerateResponse(
        yaml_script=result.yaml_script,
        mode="live",
        valid=valid,
        parse_error=parse_error,
        iterations=result.iterations,
        exploration_incomplete=result.exploration_incomplete,
        verification_passed=result.verification_passed,
        verification_attempts=result.verification_attempts,
        verification_issues=result.verification_issues or None,
        timed_out=result.timed_out,
        hit_iteration_limit=result.hit_iteration_limit,
        notes=result.notes or None,
    )


async def _generate_screenshot(
    req: GenerateRequest,
    asset_paths: list[Path],
    client: LLMClient,
) -> GenerateResponse:
    ocr_per_asset: dict[str, list[dict]] = {}
    ocr_used = False
    if _ocr_available():
        cache_dir = _work_dir() / "ocr_cache"
        for path in asset_paths:
            try:
                items, _ = await asyncio.to_thread(analyze_image, path, cache_dir)
                ocr_per_asset[path.name] = items
                ocr_used = True
            except Exception as exc:
                log.warning("[generate] OCR failed for %s: %s", path.name, exc)
                ocr_per_asset[path.name] = []

    messages = build_screenshot_prompt(
        user_description=req.task,
        asset_filenames=[p.name for p in asset_paths],
        ocr_per_asset=ocr_per_asset or None,
        asset_descriptions=req.asset_descriptions,
        voice=req.voice,
        language=req.language,
        resolution=req.resolution,
        fps=req.fps,
    )

    yaml_script = await client.complete(messages)
    yaml_script = _strip_markdown_fences(yaml_script)
    valid, parse_error = _validate_yaml(yaml_script)
    self_correction_used = False

    if not valid:
        log.info("[generate] screenshot YAML invalid, attempting self-correction: %s", parse_error)
        self_correction_used = True
        messages.append({"role": "assistant", "content": yaml_script})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"YAML невалиден. Парсер вернул ошибку:\n{parse_error}\n\n"
                    "Перегенерируй YAML, исправив именно эту ошибку. Отдай ТОЛЬКО валидный YAML, "
                    "без markdown-обёрток."
                ),
            }
        )
        yaml_script = await client.complete(messages)
        yaml_script = _strip_markdown_fences(yaml_script)
        valid, parse_error = _validate_yaml(yaml_script)

    return GenerateResponse(
        yaml_script=yaml_script,
        mode="screenshot",
        valid=valid,
        parse_error=parse_error,
        ocr_used=ocr_used,
        self_correction_used=self_correction_used,
    )


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped


def _rate_limit_value() -> str:
    return get_settings().generator_rate_limit


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(_rate_limit_value)
async def generate(request: Request, body: GenerateRequest) -> GenerateResponse:
    try:
        client = LLMClient()
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if body.mode == "live":
        _preflight_live(body)
        return await _generate_live(body, client)

    asset_paths = _preflight_screenshot(body)
    return await _generate_screenshot(body, asset_paths, client)
