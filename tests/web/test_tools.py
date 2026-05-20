from __future__ import annotations

import json

import pytest

from web.backend.app.generator.browser_agent import AgentObservation, BrowserAgentError
from web.backend.app.generator.tools import (
    TOOL_SCHEMAS,
    FinishSignal,
    execute_tool,
)


class FakeAgent:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    def _obs(self, url="https://example.com") -> AgentObservation:
        return AgentObservation(url=url, title="Example", dom="<button>OK</button>", truncated=False)

    def navigate(self, url):
        self.calls.append(("navigate", (url,), {}))
        return self._obs(url)

    def click(self, selector):
        self.calls.append(("click", (selector,), {}))
        return self._obs()

    def type_text(self, selector, text, *, submit=False):
        self.calls.append(("type_text", (selector, text), {"submit": submit}))
        return self._obs()

    def scroll(self, direction, pixels):
        self.calls.append(("scroll", (direction, pixels), {}))
        return self._obs()

    def wait(self, seconds):
        self.calls.append(("wait", (seconds,), {}))
        return self._obs()

    def observe(self):
        self.calls.append(("observe", (), {}))
        return self._obs()


def test_schemas_contain_all_required_tools():
    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert names == {"navigate", "click", "type_text", "scroll", "wait", "observe", "finish"}


def test_schemas_have_valid_json_schema_shape():
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert "name" in fn and "description" in fn and "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_navigate_returns_payload_with_url_and_dom():
    agent = FakeAgent()
    raw = execute_tool("navigate", '{"url": "https://gitflic.ru"}', agent)
    assert isinstance(raw, str)
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["url"] == "https://gitflic.ru"
    assert "dom" in payload
    assert agent.calls == [("navigate", ("https://gitflic.ru",), {})]


def test_click_passes_selector():
    agent = FakeAgent()
    raw = execute_tool("click", '{"selector": "#login"}', agent)
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert agent.calls == [("click", ("#login",), {})]


def test_type_text_with_submit():
    agent = FakeAgent()
    raw = execute_tool(
        "type_text",
        '{"selector": "input[name=q]", "text": "hello", "submit": true}',
        agent,
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert agent.calls == [("type_text", ("input[name=q]", "hello"), {"submit": True})]


def test_type_text_without_submit_defaults_false():
    agent = FakeAgent()
    execute_tool("type_text", '{"selector": "i", "text": "x"}', agent)
    assert agent.calls[-1][2] == {"submit": False}


def test_scroll_with_pixels():
    agent = FakeAgent()
    execute_tool("scroll", '{"direction": "down", "pixels": 800}', agent)
    assert agent.calls == [("scroll", ("down", 800), {})]


def test_scroll_default_pixels_500():
    agent = FakeAgent()
    execute_tool("scroll", '{"direction": "up"}', agent)
    assert agent.calls == [("scroll", ("up", 500), {})]


def test_wait_with_seconds():
    agent = FakeAgent()
    execute_tool("wait", '{"seconds": 2.5}', agent)
    assert agent.calls == [("wait", (2.5,), {})]


def test_observe_no_args():
    agent = FakeAgent()
    raw = execute_tool("observe", "", agent)
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert agent.calls == [("observe", (), {})]


def test_finish_returns_signal_no_browser_call():
    agent = FakeAgent()
    result = execute_tool(
        "finish",
        '{"yaml_script": "metadata:\\n  resolution: 1920x1080", "exploration_incomplete": true, "notes": "MVP"}',
        agent,
    )
    assert isinstance(result, FinishSignal)
    assert result.yaml_script.startswith("metadata:")
    assert result.exploration_incomplete is True
    assert result.notes == "MVP"
    assert agent.calls == []


def test_finish_defaults():
    agent = FakeAgent()
    result = execute_tool("finish", '{"yaml_script": "x"}', agent)
    assert isinstance(result, FinishSignal)
    assert result.exploration_incomplete is False
    assert result.notes == ""


def test_unknown_tool_returns_error_payload():
    agent = FakeAgent()
    raw = execute_tool("teleport", "{}", agent)
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "unknown tool" in payload["error"]
    assert agent.calls == []


def test_invalid_json_arguments():
    agent = FakeAgent()
    raw = execute_tool("navigate", "{not json}", agent)
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "JSONDecodeError" in payload["error"]


def test_missing_required_argument():
    agent = FakeAgent()
    raw = execute_tool("navigate", "{}", agent)
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "missing argument" in payload["error"]


def test_browser_agent_error_is_caught():
    class FailingAgent(FakeAgent):
        def click(self, selector):
            raise BrowserAgentError("element not found")

    raw = execute_tool("click", '{"selector": "#x"}', FailingAgent())
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "BrowserAgentError: element not found" in payload["error"]


def test_unexpected_exception_is_caught():
    class CrashingAgent(FakeAgent):
        def navigate(self, url):
            raise RuntimeError("boom")

    raw = execute_tool("navigate", '{"url": "https://x"}', CrashingAgent())
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "RuntimeError: boom" in payload["error"]
