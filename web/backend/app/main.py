from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import List

import yaml
from fastapi import FastAPI, File, HTTPException, Path as FPath, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from web.backend.app.adapter import video_to_payload
from web.backend.app.blocks import list_blocks
from web.backend.app.jobs import CeleryJobRegistry, list_output_files, public_status
from web.backend.app.schemas import (
    JobCreatedResponse,
    JobStatusResponse,
    ScriptPayload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORK_DIR = Path(os.environ.get("AAVB_WORK_DIR", PROJECT_ROOT / "web" / "backend" / "_work"))
ASSETS_DIR = WORK_DIR / "assets"
SCRIPTS_DIR = WORK_DIR / "scripts"
OUTPUTS_DIR = WORK_DIR / "outputs"
REGISTRY_DIR = WORK_DIR / "registry"
FRONTEND_DIR = PROJECT_ROOT / "web" / "frontend"
for d in (ASSETS_DIR, SCRIPTS_DIR, OUTPUTS_DIR, REGISTRY_DIR):
    d.mkdir(parents=True, exist_ok=True)

registry = CeleryJobRegistry(REGISTRY_DIR)


def _safe_name(name: str) -> str:
    base = os.path.basename(name)
    cleaned = "".join(c for c in base if c.isalnum() or c in "._-")
    if not cleaned:
        raise HTTPException(status_code=400, detail="invalid filename")
    return cleaned


def _get_record_or_404(job_id: str) -> dict:
    record = registry.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="job not found")
    return record


def _raise_validation_error(exc: ValidationError) -> None:
    raise HTTPException(status_code=422, detail=json.loads(exc.json()))


def _enqueue(script_path: str, output_dir: str) -> str:
    from core.queue.tasks import render_video_task

    async_result = render_video_task.delay(script_path, output_dir)
    return async_result.id


def _job_status(job_id: str) -> JobStatusResponse:
    record = _get_record_or_404(job_id)

    from core.queue.celery_app import celery_app

    async_result = celery_app.AsyncResult(job_id)
    status = public_status(async_result.state)
    error = None
    started_at = None
    finished_at = None

    if async_result.failed():
        try:
            error = repr(async_result.result)
        except Exception:
            error = "task failed"

    info = async_result.info if isinstance(async_result.info, dict) else {}
    if info:
        started_at = info.get("started_at")

    if async_result.ready():
        finished_at = time.time()

    return JobStatusResponse(
        job_id=job_id,
        status=status,
        created_at=record["created_at"],
        started_at=started_at,
        finished_at=finished_at,
        error=error,
        output_dir=record["output_dir"],
        output_files=list_output_files(record["output_dir"]),
        log_tail=[],
    )


def create_app() -> FastAPI:
    app = FastAPI(title="AA Video Builder Web", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "service": "aa-video-builder-web"}

    @app.get("/api/blocks")
    def get_blocks() -> dict:
        return {"blocks": [b.model_dump() for b in list_blocks()]}

    @app.post("/api/assets")
    async def upload_asset(
        file: UploadFile | None = File(None),
        files: List[UploadFile] | None = File(None),
    ) -> dict:
        items: List[UploadFile] = []
        if files:
            items.extend(files)
        if file:
            items.append(file)
        if not items:
            raise HTTPException(status_code=400, detail="missing file")
        saved = []
        for f in items:
            if not f.filename:
                continue
            name = _safe_name(f.filename)
            target = ASSETS_DIR / name
            with target.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            saved.append({"filename": name, "path": str(target)})
        if len(saved) == 1:
            return saved[0]
        return {"saved": saved}

    @app.get("/api/assets")
    def list_assets() -> dict:
        items = []
        for entry in sorted(ASSETS_DIR.iterdir()):
            if entry.is_file():
                items.append({
                    "filename": entry.name,
                    "path": str(entry),
                    "size": entry.stat().st_size,
                })
        return {"assets": items}

    @app.delete("/api/assets/{name}")
    def delete_asset(name: str = FPath(...)) -> dict:
        name = _safe_name(name)
        target = ASSETS_DIR / name
        if not target.exists():
            raise HTTPException(status_code=404, detail="asset not found")
        target.unlink()
        return {"deleted": name}

    @app.post("/api/scripts/preview")
    def preview_script(payload: dict) -> dict:
        try:
            script = ScriptPayload(**payload)
        except ValidationError as exc:
            _raise_validation_error(exc)
        text = yaml.safe_dump(script.to_yaml_dict(), allow_unicode=True, sort_keys=False)
        return {"yaml": text}

    @app.post("/api/scripts/parse")
    async def parse_script(file: UploadFile = File(...)) -> dict:
        if not file.filename or not file.filename.lower().endswith((".yml", ".yaml")):
            raise HTTPException(status_code=400, detail="ожидается файл с расширением .yml/.yaml")

        raw = await file.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="файл должен быть в UTF-8")

        tmp = SCRIPTS_DIR / f"_upload_{int(time.time() * 1000)}.yaml"
        tmp.write_text(text, encoding="utf-8")
        try:
            from core.parser import parse as parse_yaml

            video = parse_yaml(str(tmp))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"ошибка парсинга YAML: {exc}")
        finally:
            tmp.unlink(missing_ok=True)

        if video.metadata.mode != "screenshot":
            raise HTTPException(
                status_code=422,
                detail=f"web-сервис поддерживает только mode=screenshot (получено: {video.metadata.mode})",
            )

        try:
            payload = video_to_payload(video)
        except ValidationError as exc:
            _raise_validation_error(exc)

        existing_assets = {p.name for p in ASSETS_DIR.iterdir() if p.is_file()}
        missing = [s.path for s in payload.scenes if s.path and s.path not in existing_assets]

        return {
            "payload": payload.model_dump(),
            "yaml": text,
            "missing_assets": sorted(set(missing)),
        }

    @app.post("/api/jobs", response_model=JobCreatedResponse)
    def create_job(payload: dict) -> JobCreatedResponse:
        try:
            script = ScriptPayload(**payload)
        except ValidationError as exc:
            _raise_validation_error(exc)

        for scene in script.scenes:
            asset = ASSETS_DIR / os.path.basename(scene.path)
            if not asset.exists():
                raise HTTPException(
                    status_code=400,
                    detail=f"asset not found: {scene.path} (upload via POST /api/assets first)",
                )
            scene.path = str(asset)

        job_id_seed = f"{int(time.time() * 1000)}_{script.metadata.title}"
        script_filename = _safe_name(f"{job_id_seed}.yaml")
        script_path = SCRIPTS_DIR / script_filename
        with script_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(script.to_yaml_dict(), fh, allow_unicode=True, sort_keys=False)

        out_dir = OUTPUTS_DIR / script_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        task_id = _enqueue(str(script_path), str(out_dir))
        registry.add(task_id, str(script_path), str(out_dir))
        return JobCreatedResponse(job_id=task_id)

    @app.get("/api/jobs", response_model=List[JobStatusResponse])
    def list_jobs() -> List[JobStatusResponse]:
        return [_job_status(rec["job_id"]) for rec in registry.list()]

    @app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
    def get_job(job_id: str) -> JobStatusResponse:
        return _job_status(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        _get_record_or_404(job_id)
        from core.queue.celery_app import celery_app

        celery_app.control.revoke(job_id, terminate=True, signal="SIGTERM")
        return {"cancelled": job_id}

    @app.get("/api/jobs/{job_id}/files/{name}")
    def get_job_file(job_id: str, name: str) -> FileResponse:
        record = _get_record_or_404(job_id)
        safe = _safe_name(name)
        full = Path(record["output_dir"]) / safe
        if not full.exists() or not full.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(str(full), filename=safe)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app


app = create_app()
