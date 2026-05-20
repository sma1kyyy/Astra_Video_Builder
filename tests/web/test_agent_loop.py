from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from web.backend.app.generator.agent_loop import AgentLoopResult, run_agent_loop
from web.backend.app.generator.browser_agent import AgentObservation
from web.backend.app.generator.llm_client import ToolCall, ToolChatResult


class FakeBrowserAgent:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def _obs(self, url="https://example.com"):
        return AgentObservation(url=url, title="T", dom="<button>OK</button>", truncated=False)

    def navigate(self, url):
        self.calls.append(("navigate", (url,)))
        return self._obs(url)

    def click(self, selector):
        self.calls.append(("click", (selector,)))
        return self._obs()

    def type_text(self, selector, text, *, submit=False):
        self.calls.append(("type_text", (selector, text, submit)))
        return self._obs()

    def scroll(self, direction, pixels):
        self.calls.append(("scroll", (direction, pixels)))
        return self._obs()

    def wait(self, seconds):
        self.calls.append(("wait", (seconds,)))
        return self._obs()

    def observe(self):
        self.calls.append(("observe", ()))
        return self._obs()


@contextmanager
def fake_agent_cm(agent):
    yield agent


class ScriptedLLM:
    """Replays a scripted list of (content, [ToolCall]) tuples per call."""

    def __init__(self, scripted: list[tuple[str | None, list[ToolCall]]]):
        self._scripted = list(scripted)
        self.calls: list[dict] = []

    async def chat_with_tools(self, messages, tools, *, temperature=0.2, tool_choice="auto"):
        self.calls.append({"messages": list(messages), "tool_choice": tool_choice})
        if not self._scripted:
            return ToolChatResult(content="empty", tool_calls=[])
        content, calls = self._scripted.pop(0)
        return ToolChatResult(content=content, tool_calls=calls, finish_reason="tool_calls" if calls else "stop")


def _tc(call_id, name, args):
    return ToolCall(id=call_id, name=name, arguments=args)


@pytest.mark.asyncio
async def test_loop_finishes_on_first_finish_call():
    agent = FakeBrowserAgent()
    llm = ScriptedLLM(
        [
            (
                "Исследую сайт",
                [_tc("c1", "navigate", '{"url": "https://gitflic.ru"}')],
            ),
            (
                "Готово",
                [
                    _tc(
                        "c2",
                        "finish",
                        '{"yaml_script": "metadata:\\n  ok: true", "notes": "done"}',
                    )
                ],
            ),
        ]
    )

    result = await run_agent_loop(
        task_description="t",
        start_url="https://x",
        user_prompt="p",
        llm_client=llm,
        verification_retries=0,
        agent_factory=lambda: fake_agent_cm(agent),
    )

    second_call_messages = llm.calls[1]["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "c1"
    assert '"ok": true' in tool_msgs[0]["content"]


@pytest.mark.asyncio
async def test_loop_hits_iteration_limit_and_forces_finish():
    agent = FakeBrowserAgent()
    looping_call = ("step", [_tc("c", "navigate", '{"url": "https://x"}')])
    scripted = [looping_call] * 3
    scripted.append(
        (
            "forced",
            [_tc("cf", "finish", '{"yaml_script": "minimal", "exploration_incomplete": true, "notes": "limit"}')],
        )
    )
    llm = ScriptedLLM(scripted)

    result = await run_agent_loop(
        task_description="t",
        start_url="https://x",
        user_prompt="p",
        llm_client=llm,
        max_iterations=3,
        agent_factory=lambda: fake_agent_cm(agent),
    )

    assert result.hit_iteration_limit is True
    assert result.exploration_incomplete is True
    assert result.yaml_script == "minimal"
    assert result.notes == "limit"
    assert result.iterations == 3
    forced_call = llm.calls[-1]
    assert isinstance(forced_call["tool_choice"], dict)
    assert forced_call["tool_choice"]["function"]["name"] == "finish"


@pytest.mark.asyncio
async def test_loop_handles_no_tool_calls_with_warning_message():
    agent = FakeBrowserAgent()
    llm = ScriptedLLM(
        [
            ("just talking", []),
            ("ok finishing", [_tc("c1", "finish", '{"yaml_script": "y"}')]),
        ]
    )

    result = await run_agent_loop(
        task_description="t",
        start_url="https://x",
        user_prompt="p",
        llm_client=llm,
        max_iterations=10,
        verification_retries=0,
        agent_factory=lambda: fake_agent_cm(agent),
    )

    assert result.yaml_script == "y"
    second_call_messages = llm.calls[1]["messages"]
    last_user_msgs = [m for m in second_call_messages if m.get("role") == "user"]
    assert any("СИСТЕМНОЕ СООБЩЕНИЕ" in (m.get("content") or "") for m in last_user_msgs)


@pytest.mark.asyncio
async def test_loop_handles_failed_tool_calls_in_transcript():
    class FailingAgent(FakeBrowserAgent):
        def click(self, selector):
            from web.backend.app.generator.browser_agent import BrowserAgentError

            raise BrowserAgentError(f"element not found: {selector}")

    agent = FailingAgent()
    llm = ScriptedLLM(
        [
            ("trying", [_tc("c1", "click", '{"selector": "#missing"}')]),
            ("falling back", [_tc("c2", "finish", '{"yaml_script": "y"}')]),
        ]
    )

    result = await run_agent_loop(
        task_description="t",
        start_url="https://x",
        user_prompt="p",
        llm_client=llm,
        verification_retries=0,
        agent_factory=lambda: fake_agent_cm(agent),
    )

    assert len(result.transcript) == 2
    click_trace = result.transcript[0]
    assert click_trace.tool == "click"
    assert click_trace.ok is False
    assert "element not found" in click_trace.error


@pytest.mark.asyncio
async def test_loop_timeout_triggers_forced_finish():
    agent = FakeBrowserAgent()

    class SlowLLM(ScriptedLLM):
        async def chat_with_tools(self, messages, tools, *, temperature=0.2, tool_choice="auto"):
            if tool_choice == "auto":
                await asyncio.sleep(0.5)
            return await super().chat_with_tools(
                messages, tools, temperature=temperature, tool_choice=tool_choice
            )

    llm = SlowLLM(
        [
            ("forced", [_tc("c", "finish", '{"yaml_script": "x", "exploration_incomplete": true}')]),
        ]
    )

    result = await run_agent_loop(
        task_description="t",
        start_url="https://x",
        user_prompt="p",
        llm_client=llm,
        max_iterations=10,
        total_timeout=0.1,
        iteration_timeout=0.05,
        agent_factory=lambda: fake_agent_cm(agent),
    )

    assert result.timed_out is True
    assert result.yaml_script == "x"
    assert result.exploration_incomplete is True


@pytest.mark.asyncio
async def test_loop_executes_multiple_tool_calls_in_one_assistant_turn():
    agent = FakeBrowserAgent()
    llm = ScriptedLLM(
        [
            (
                "two actions",
                [
                    _tc("c1", "navigate", '{"url": "https://x"}'),
                    _tc("c2", "wait", '{"seconds": 1}'),
                ],
            ),
            ("done", [_tc("c3", "finish", '{"yaml_script": "y"}')]),
        ]
    )

    result = await run_agent_loop(
        task_description="t",
        start_url="https://x",
        user_prompt="p",
        llm_client=llm,
        verification_retries=0,
        agent_factory=lambda: fake_agent_cm(agent),
    )

    assert agent.calls == [
        ("navigate", ("https://x",)),
        ("wait", (1.0,)),
    ]
    assert [t.tool for t in result.transcript[:2]] == ["navigate", "wait"]
