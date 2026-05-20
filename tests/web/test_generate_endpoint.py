from __future__ import annotations

import io

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from web.backend.app.generator.agent_loop import AgentLoopResult


_VALID_LIVE_YAML = """\
metadata:
  title: test
  resolution: 1920x1080
  mode: live
  browser: chrome
  fps: 30
  language: ru

acts:
  act_1:
    name: a
    scenes:
      scene_1:
        name: s
        duration: 5
        actions:
          action_1:
            type: navigate
            url: https://example.com
"""


_VALID_SCREENSHOT_YAML = """\
metadata:
  title: test
  resolution: 1920x1080
  mode: screenshot
  fps: 24
  language: ru

acts:
  act_1:
    name: a
    scenes:
      scene_1:
        name: s
        path: input/shot.png
        duration: 4
"""


def _patch_llm_configured(monkeypatch):
    from web.backend.app.generator import config as cfg_mod, llm_client as llm_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("GENERATOR_RATE_LIMIT", "100/minute")

    class FakeOpenAI:
        def __init__(self, *a, **kw):
            pass

    monkeypatch.setattr(llm_mod, "AsyncOpenAI", FakeOpenAI)


def test_generate_requires_start_url_for_live(client, monkeypatch):
    _patch_llm_configured(monkeypatch)
    res = client.post(
        "/api/generator/generate",
        json={"mode": "live", "task": "open example"},
    )
    assert res.status_code == 400
    assert "start_url" in res.json()["detail"]


def test_generate_requires_valid_url_scheme(client, monkeypatch):
    _patch_llm_configured(monkeypatch)
    res = client.post(
        "/api/generator/generate",
        json={"mode": "live", "task": "open example", "start_url": "example.com"},
    )
    assert res.status_code == 400
    assert "http://" in res.json()["detail"]


def test_generate_requires_task(client, monkeypatch):
    _patch_llm_configured(monkeypatch)
    res = client.post(
        "/api/generator/generate",
        json={"mode": "live", "task": "", "start_url": "https://x"},
    )
    assert res.status_code == 422


def test_generate_requires_assets_for_screenshot(client, monkeypatch):
    _patch_llm_configured(monkeypatch)
    res = client.post(
        "/api/generator/generate",
        json={"mode": "screenshot", "task": "demo"},
    )
    assert res.status_code == 400
    assert "asset_filenames" in res.json()["detail"]


def test_generate_screenshot_404_on_missing_asset(client, monkeypatch):
    _patch_llm_configured(monkeypatch)
    res = client.post(
        "/api/generator/generate",
        json={"mode": "screenshot", "task": "demo", "asset_filenames": ["nope.png"]},
    )
    assert res.status_code == 404


def test_generate_returns_503_without_llm_key(client, monkeypatch):
    from web.backend.app.generator import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_API_KEY", "")
    res = client.post(
        "/api/generator/generate",
        json={"mode": "live", "task": "demo", "start_url": "https://x"},
    )
    assert res.status_code == 503


def test_generate_live_happy_path(client, monkeypatch):
    _patch_llm_configured(monkeypatch)

    async def fake_run_agent_loop(**kwargs):
        return AgentLoopResult(
            yaml_script=_VALID_LIVE_YAML,
            exploration_incomplete=False,
            iterations=5,
            notes="ok",
            transcript=[],
            verification_passed=True,
            verification_attempts=1,
        )

    from web.backend.app.generator import router as router_mod

    monkeypatch.setattr(router_mod, "run_agent_loop", fake_run_agent_loop)

    res = client.post(
        "/api/generator/generate",
        json={
            "mode": "live",
            "task": "open example",
            "start_url": "https://example.com",
            "max_iterations": 5,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "live"
    assert body["valid"] is True
    assert body["parse_error"] is None
    assert body["iterations"] == 5
    assert body["verification_passed"] is True
    assert body["verification_attempts"] == 1
    assert body["exploration_incomplete"] is False


def test_generate_live_invalid_yaml_reports_parse_error(client, monkeypatch):
    _patch_llm_configured(monkeypatch)

    async def fake_run_agent_loop(**kwargs):
        return AgentLoopResult(
            yaml_script="not: valid: yaml: :",
            exploration_incomplete=True,
            iterations=20,
            notes="failed",
            transcript=[],
            verification_passed=False,
            verification_attempts=2,
            verification_issues=["a/b: not found"],
            hit_iteration_limit=True,
        )

    from web.backend.app.generator import router as router_mod

    monkeypatch.setattr(router_mod, "run_agent_loop", fake_run_agent_loop)

    res = client.post(
        "/api/generator/generate",
        json={"mode": "live", "task": "t", "start_url": "https://x"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is False
    assert body["parse_error"] is not None
    assert body["verification_passed"] is False
    assert body["verification_issues"] == ["a/b: not found"]
    assert body["hit_iteration_limit"] is True


def test_generate_screenshot_happy_path(client, monkeypatch):
    _patch_llm_configured(monkeypatch)

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buf, format="PNG")
    buf.seek(0)
    upload = client.post(
        "/api/assets",
        files={"file": ("shot.png", buf, "image/png")},
    )
    assert upload.status_code == 200

    from web.backend.app.generator import router as router_mod

    async def fake_complete(self, messages, **kwargs):
        return _VALID_SCREENSHOT_YAML

    monkeypatch.setattr(router_mod.LLMClient, "complete", fake_complete)

    def fake_ocr_available():
        return False

    monkeypatch.setattr(router_mod, "_ocr_available", fake_ocr_available)

    res = client.post(
        "/api/generator/generate",
        json={
            "mode": "screenshot",
            "task": "show login",
            "asset_filenames": ["shot.png"],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "screenshot"
    assert body["valid"] is True
    assert body["self_correction_used"] is False
    assert body["ocr_used"] is False


def test_generate_screenshot_self_correction(client, monkeypatch):
    _patch_llm_configured(monkeypatch)

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buf, format="PNG")
    buf.seek(0)
    client.post("/api/assets", files={"file": ("shot2.png", buf, "image/png")})

    from web.backend.app.generator import router as router_mod

    calls = {"n": 0}

    async def fake_complete(self, messages, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not: valid: yaml: :"
        return _VALID_SCREENSHOT_YAML

    monkeypatch.setattr(router_mod.LLMClient, "complete", fake_complete)
    monkeypatch.setattr(router_mod, "_ocr_available", lambda: False)

    res = client.post(
        "/api/generator/generate",
        json={
            "mode": "screenshot",
            "task": "demo",
            "asset_filenames": ["shot2.png"],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["valid"] is True
    assert body["self_correction_used"] is True
    assert calls["n"] == 2


def test_generate_strips_markdown_fences(client, monkeypatch):
    _patch_llm_configured(monkeypatch)

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buf, format="PNG")
    buf.seek(0)
    client.post("/api/assets", files={"file": ("shot3.png", buf, "image/png")})

    from web.backend.app.generator import router as router_mod

    async def fake_complete(self, messages, **kwargs):
        return f"```yaml\n{_VALID_SCREENSHOT_YAML}\n```"

    monkeypatch.setattr(router_mod.LLMClient, "complete", fake_complete)
    monkeypatch.setattr(router_mod, "_ocr_available", lambda: False)

    res = client.post(
        "/api/generator/generate",
        json={
            "mode": "screenshot",
            "task": "demo",
            "asset_filenames": ["shot3.png"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert not body["yaml_script"].startswith("```")
