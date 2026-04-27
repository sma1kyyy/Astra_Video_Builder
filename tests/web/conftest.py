import shutil
import sys
from pathlib import Path

import pytest


@pytest.fixture
def web_workdir(monkeypatch):
    workdir = Path("web/backend/_work_test").resolve()
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("AAVB_WORK_DIR", str(workdir))
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")

    for mod in [m for m in list(sys.modules) if m.startswith("web.backend") or m.startswith("core.queue")]:
        del sys.modules[mod]

    from core.queue.celery_app import celery_app
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=False,
    )

    from web.backend.app import main as web_main

    yield workdir, web_main

    for mod in [m for m in list(sys.modules) if m.startswith("web.backend") or m.startswith("core.queue")]:
        del sys.modules[mod]

    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture
def client(web_workdir):
    from fastapi.testclient import TestClient

    _, web_main = web_workdir
    with TestClient(web_main.app) as c:
        yield c
