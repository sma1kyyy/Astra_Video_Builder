from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class CeleryJobRegistry:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        safe = "".join(c for c in job_id if c.isalnum() or c in "._-")
        return self.root / f"{safe}.json"

    def add(self, job_id: str, script_path: str, output_dir: str) -> Dict[str, Any]:
        record = {
            "job_id": job_id,
            "script_path": script_path,
            "output_dir": output_dir,
            "created_at": time.time(),
        }
        with self._path(job_id).open("w", encoding="utf-8") as fh:
            json.dump(record, fh)
        return record

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(job_id)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def list(self) -> List[Dict[str, Any]]:
        records = []
        for entry in self.root.glob("*.json"):
            try:
                with entry.open(encoding="utf-8") as fh:
                    records.append(json.load(fh))
            except Exception:
                continue
        records.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        return records


_CELERY_TO_PUBLIC = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "done",
    "FAILURE": "failed",
    "REVOKED": "cancelled",
}


def public_status(state: str) -> str:
    return _CELERY_TO_PUBLIC.get(state, state.lower())


def list_output_files(output_dir: str) -> List[str]:
    files: List[str] = []
    if output_dir and os.path.isdir(output_dir):
        for entry in sorted(os.listdir(output_dir)):
            full = os.path.join(output_dir, entry)
            if os.path.isfile(full):
                files.append(entry)
    return files
