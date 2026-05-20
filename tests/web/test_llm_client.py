from __future__ import annotations

from types import SimpleNamespace

import pytest

from web.backend.app.generator.llm_client import LLMClient, LLMNotConfiguredError, _merge_choices


def _make_choice(content=None, tool_calls=None, finish_reason=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(message=msg, finish_reason=finish_reason)


def _make_tool_call(call_id, name, arguments):
    func = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, function=func)


def test_merge_choices_single_message_with_text_and_tools():
    tc = _make_tool_call("t1", "navigate", '{"url":"https://x"}')
    resp = SimpleNamespace(choices=[_make_choice("hello", [tc], "tool_calls")])

    result = _merge_choices(resp)

    assert result.content == "hello"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "t1"
    assert result.tool_calls[0].name == "navigate"
    assert result.tool_calls[0].arguments == '{"url":"https://x"}'
    assert result.finish_reason == "tool_calls"


def test_merge_choices_provider_splits_text_and_tools_across_choices():
    tc = _make_tool_call("tooluse_abc", "click", '{"selector":"#btn"}')
    resp = SimpleNamespace(
        choices=[
            _make_choice("Конечно, кликаю!", None, "tool_calls"),
            _make_choice(None, [tc], "tool_calls"),
        ]
    )

    result = _merge_choices(resp)

    assert result.content == "Конечно, кликаю!"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "click"
    assert result.finish_reason == "tool_calls"


def test_merge_choices_multiple_tool_calls():
    tc1 = _make_tool_call("a", "navigate", "{}")
    tc2 = _make_tool_call("b", "click", "{}")
    resp = SimpleNamespace(
        choices=[
            _make_choice("planning", None, "tool_calls"),
            _make_choice(None, [tc1, tc2], "tool_calls"),
        ]
    )

    result = _merge_choices(resp)

    assert len(result.tool_calls) == 2
    assert [c.name for c in result.tool_calls] == ["navigate", "click"]


def test_merge_choices_text_only():
    resp = SimpleNamespace(choices=[_make_choice("just text", None, "stop")])

    result = _merge_choices(resp)

    assert result.content == "just text"
    assert result.tool_calls == []
    assert result.finish_reason == "stop"


def test_merge_choices_empty():
    resp = SimpleNamespace(choices=[])

    result = _merge_choices(resp)

    assert result.content is None
    assert result.tool_calls == []
    assert result.finish_reason is None


def test_llm_client_raises_when_not_configured(monkeypatch):
    from web.backend.app.generator import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_API_KEY", "")

    with pytest.raises(LLMNotConfiguredError):
        LLMClient(cfg_mod.GeneratorSettings(LLM_API_KEY=""))
