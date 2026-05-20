import io
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("celery")


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_blocks_catalog(client):
    res = client.get("/api/blocks")
    assert res.status_code == 200
    ids = [b["id"] for b in res.json()["blocks"]]
    assert {"metadata", "scene", "annotation"}.issubset(ids)


def test_assets_upload_list_delete(client):
    res = client.post(
        "/api/assets",
        files={"file": ("hello.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["filename"] == "hello.png"

    listed = client.get("/api/assets").json()["assets"]
    assert any(a["filename"] == "hello.png" for a in listed)

    deleted = client.delete("/api/assets/hello.png")
    assert deleted.status_code == 200
    assert client.delete("/api/assets/hello.png").status_code == 404


def test_preview_validates_payload(client):
    bad = {"metadata": {"title": "bad name!"}, "scenes": []}
    res = client.post("/api/scripts/preview", json=bad)
    assert res.status_code == 422


def test_preview_yaml_includes_screenshot_mode(client):
    payload = {
        "metadata": {"title": "demo", "resolution": "1920x1080", "fps": 24},
        "scenes": [{"name": "s1", "path": "screen1.png", "duration": 2.0}],
    }
    res = client.post("/api/scripts/preview", json=payload)
    assert res.status_code == 200
    yaml_text = res.json()["yaml"]
    assert "mode: screenshot" in yaml_text
    assert "scene_1" in yaml_text


def test_create_job_requires_uploaded_asset(client):
    payload = {
        "metadata": {"title": "demo", "resolution": "1920x1080", "fps": 24},
        "scenes": [{"name": "s1", "path": "missing.png", "duration": 2.0}],
    }
    res = client.post("/api/jobs", json=payload)
    assert res.status_code == 400


def test_create_job_dispatches_to_celery(client, web_workdir, monkeypatch):
    _, web_main = web_workdir

    captured = {}

    def fake_delay(script_path, output_dir):
        captured["script_path"] = script_path
        captured["output_dir"] = output_dir
        with open(f"{output_dir}/result.txt", "w") as f:
            f.write("ok")

        class _R:
            id = "fake-task-id-123"
            state = "SUCCESS"
            info = None
            result = {"status": "success"}

            def ready(self): return True
            def successful(self): return True
            def failed(self): return False
        return _R()

    from core.queue import tasks as task_mod
    monkeypatch.setattr(task_mod.render_video_task, "delay", fake_delay)

    client.post(
        "/api/assets",
        files={"file": ("screen1.png", io.BytesIO(b"\x89PNG"), "image/png")},
    )

    payload = {
        "metadata": {"title": "demo", "resolution": "1920x1080", "fps": 24},
        "scenes": [{"name": "s1", "path": "screen1.png", "duration": 2.0}],
    }
    res = client.post("/api/jobs", json=payload)
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert job_id == "fake-task-id-123"
    assert captured["script_path"].endswith(".yaml")

    snap = client.get(f"/api/jobs/{job_id}").json()
    assert snap["job_id"] == job_id
    assert "result.txt" in snap["output_files"]

    file_res = client.get(f"/api/jobs/{job_id}/files/result.txt")
    assert file_res.status_code == 200
    assert file_res.text == "ok"


def test_unknown_job_returns_404(client):
    assert client.get("/api/jobs/does-not-exist").status_code == 404
    assert client.post("/api/jobs/does-not-exist/cancel").status_code == 404


def test_job_status_maps_celery_states(client, web_workdir, monkeypatch):
    _, web_main = web_workdir
    web_main.registry.add("running-id", "/tmp/x.yaml", str(web_main.OUTPUTS_DIR))

    from core.queue.celery_app import celery_app

    class _AR:
        state = "STARTED"
        info = {"started_at": 123.0}
        result = None

        def ready(self): return False
        def failed(self): return False

    monkeypatch.setattr(celery_app, "AsyncResult", lambda _id: _AR())

    snap = client.get("/api/jobs/running-id").json()
    assert snap["status"] == "running"
    assert snap["started_at"] == 123.0


def test_job_cancel_revokes_celery_task(client, web_workdir, monkeypatch):
    _, web_main = web_workdir
    web_main.registry.add("revoke-me", "/tmp/x.yaml", str(web_main.OUTPUTS_DIR))

    revoked = {}
    from core.queue.celery_app import celery_app

    def fake_revoke(task_id, terminate=False, signal=None):
        revoked["id"] = task_id
        revoked["terminate"] = terminate
        revoked["signal"] = signal

    monkeypatch.setattr(celery_app.control, "revoke", fake_revoke)

    res = client.post("/api/jobs/revoke-me/cancel")
    assert res.status_code == 200
    assert revoked["id"] == "revoke-me"
    assert revoked["terminate"] is True


def test_jobs_list_returns_registered(client, web_workdir, monkeypatch):
    _, web_main = web_workdir
    web_main.registry.add("a", "/tmp/a.yaml", str(web_main.OUTPUTS_DIR))
    web_main.registry.add("b", "/tmp/b.yaml", str(web_main.OUTPUTS_DIR))

    from core.queue.celery_app import celery_app

    class _AR:
        state = "PENDING"
        info = None
        def ready(self): return False
        def failed(self): return False

    monkeypatch.setattr(celery_app, "AsyncResult", lambda _id: _AR())

    data = client.get("/api/jobs").json()
    ids = {item["job_id"] for item in data}
    assert ids == {"a", "b"}
    assert all(item["status"] == "queued" for item in data)


VALID_YAML = """\
metadata:
  title: demo
  resolution: 1920x1080
  mode: screenshot
  fps: 24
  language: ru

acts:
  act_1:
    name: main
    scenes:
      scene_1:
        name: intro
        path: input/screen1.png
        duration: 2.0
        voice: jane
        subtitles: false
        subtitle_style: classic
        subtitle_font_size: 40
        transition: without
"""


def test_parse_yaml_normalizes_path_and_lists_missing(client):
    res = client.post(
        "/api/scripts/parse",
        files={"file": ("script.yaml", io.BytesIO(VALID_YAML.encode("utf-8")), "text/yaml")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["payload"]["scenes"][0]["path"] == "screen1.png"
    assert data["missing_assets"] == ["screen1.png"]


def test_parse_yaml_no_missing_when_asset_uploaded(client):
    client.post(
        "/api/assets",
        files={"file": ("screen1.png", io.BytesIO(b"\x89PNG"), "image/png")},
    )
    res = client.post(
        "/api/scripts/parse",
        files={"file": ("script.yaml", io.BytesIO(VALID_YAML.encode("utf-8")), "text/yaml")},
    )
    assert res.status_code == 200
    assert res.json()["missing_assets"] == []


def test_parse_yaml_rejects_non_yaml_extension(client):
    res = client.post(
        "/api/scripts/parse",
        files={"file": ("oops.txt", io.BytesIO(b"foo"), "text/plain")},
    )
    assert res.status_code == 400


def test_parse_yaml_rejects_invalid_content(client):
    res = client.post(
        "/api/scripts/parse",
        files={"file": ("bad.yaml", io.BytesIO(b"this: is: not: valid"), "text/yaml")},
    )
    assert res.status_code == 422


def test_parse_yaml_rejects_live_mode(client):
    live_yaml = VALID_YAML.replace("mode: screenshot", "mode: live")
    res = client.post(
        "/api/scripts/parse",
        files={"file": ("live.yaml", io.BytesIO(live_yaml.encode("utf-8")), "text/yaml")},
    )
    assert res.status_code == 422
    assert "screenshot" in res.json()["detail"].lower()


def test_assets_bulk_upload(client):
    res = client.post(
        "/api/assets",
        files=[
            ("files", ("a.png", io.BytesIO(b"\x89PNG"), "image/png")),
            ("files", ("b.png", io.BytesIO(b"\x89PNG"), "image/png")),
        ],
    )
    assert res.status_code == 200
    listed = client.get("/api/assets").json()["assets"]
    names = {a["filename"] for a in listed}
    assert {"a.png", "b.png"}.issubset(names)


def test_generator_status_endpoint(client):
    res = client.get("/api/generator/status")
    assert res.status_code == 200
    body = res.json()
    assert "llm_configured" in body
    assert "vision_enabled" in body
    assert "ocr_available" in body
    assert "rate_limit" in body
    assert isinstance(body["llm_configured"], bool)
    assert isinstance(body["vision_enabled"], bool)
    assert isinstance(body["ocr_available"], bool)
