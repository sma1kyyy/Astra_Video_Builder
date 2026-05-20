from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from web.backend.app.generator.browser_agent import BrowserAgent
from web.backend.app.generator.llm_client import LLMClient, ToolCall, ToolChatResult
from web.backend.app.generator.prompts import build_live_spec_block
from web.backend.app.generator.tools import TOOL_SCHEMAS, FinishSignal, execute_tool
from web.backend.app.generator.yaml_verifier import (
    VerificationResult,
    format_issues_for_llm,
    verify_yaml_by_replay,
)

log = logging.getLogger(__name__)


DEFAULT_MAX_ITERATIONS = 20
DEFAULT_TOTAL_TIMEOUT = 120.0
DEFAULT_ITERATION_TIMEOUT = 45.0
DEFAULT_TOOL_TIMEOUT = 30.0
DEFAULT_VERIFICATION_RETRIES = 2
DEFAULT_VERIFICATION_TIMEOUT = 60.0


@dataclass
class ToolTrace:
    tool: str
    arguments: str
    ok: bool
    error: str | None = None


@dataclass
class AgentLoopResult:
    yaml_script: str
    exploration_incomplete: bool
    iterations: int
    notes: str
    transcript: list[ToolTrace] = field(default_factory=list)
    timed_out: bool = False
    hit_iteration_limit: bool = False
    verification_attempts: int = 0
    verification_passed: bool = False
    verification_issues: list[str] = field(default_factory=list)


_SYSTEM_PROMPT = """Ты — ассистент-исследователь, который генерирует YAML-скрипты \
для системы записи браузерных демо-видео (aa-video-builder, режим Live Recording).

ТВОЯ ЗАДАЧА:
1. С помощью предоставленных тулов (navigate/click/type_text/scroll/wait/observe) РЕАЛЬНО \
исследуй сайт и убедись в правильности каждого селектора, который попадёт в финальный YAML.
2. После каждого действия ты получаешь компактный DOM-листинг с интерактивными элементами и их \
реальными атрибутами (id, name, data-testid, role, aria-label и т.д.).
3. Если сайт многошаговый (нажать → перейти на другую страницу → нажать ещё раз), пройди этот \
путь сам в браузере, наблюдая DOM на каждом шаге.
4. Когда ты УВЕРЕН во всех селекторах и понимаешь весь путь — вызови `finish(yaml_script=...)` \
с готовым YAML.

ЖЁСТКИЕ ПРАВИЛА ПО СЕЛЕКТОРАМ (нарушение = провал задачи):
- КАЖДЫЙ селектор в финальном YAML обязан буквально присутствовать в одном из последних \
наблюдаемых DOM-снимков. Если ты не видел селектор в DOM — НЕ ПИШИ его в YAML.
- НЕ используй селекторы из «общих знаний» о том, как обычно устроены подобные сайты. \
Site может быть любым.
- НЕ используй селекторы вида `//input[@placeholder='X' or @type='Y' or contains(@class,'Z')]` — \
это всегда галлюцинация. Только точечные селекторы из реального DOM.
- Если в очередном observe ты получил `likely_unrendered=true` или `element_count<5` — это SPA, \
ещё не отрендерившаяся. ОБЯЗАТЕЛЬНО вызови wait(3) и observe() ещё раз. Не строй селекторы по \
пустому/полупустому снимку.
- Если 3 раза подряд страница возвращает пустой DOM, или результаты поиска не появляются — \
страница вероятно SPA с асинхронной фильтрацией. Не выдумывай заведомо работающий селектор, \
лучше пропусти это действие и упрости YAML.

ЕСЛИ НЕ ПОЛУЧАЕТСЯ:
- Не петляй по одним и тем же URL. Если URL вернул 404 / пустой контент — это сигнал, что путь \
неверный. Признай это и попробуй принципиально другой подход (например, поиск через интерфейс \
вместо угадывания URL).
- При исчерпании лимита итераций вызови finish с exploration_incomplete=true и отдай MVP \
ТОЛЬКО из реально проверенных шагов. Лучше короткий рабочий YAML чем длинный с выдуманными селекторами.
- Если запрошенного ресурса нет (не найден проект, страница не существует) — честно отрази это в \
notes и отдай MVP с тем что реально доступно.

ФОРМАТ YAML (live mode):
Строго следуй формату YAML из user-промпта (там few-shot примеры и спецификация полей)."""


def _force_finish_message(reason: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": (
            f"СИСТЕМНОЕ СООБЩЕНИЕ: {reason}. "
            "Немедленно вызови finish() с самым полным рабочим YAML, который ты можешь "
            "собрать на основе уже исследованного. Установи exploration_incomplete=true "
            "и опиши в notes, чего ты не успел проверить."
        ),
    }


def _assistant_message_from_result(result: ToolChatResult) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": result.content,
        "tool_calls": [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": c.arguments},
            }
            for c in result.tool_calls
        ],
    }


def _tool_message(call: ToolCall, payload: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call.id, "content": payload}


def _trace_from(call: ToolCall, payload: str) -> ToolTrace:
    ok = '"ok": true' in payload or '"ok":true' in payload
    error: str | None = None
    if not ok:
        try:
            import json

            error = json.loads(payload).get("error")
        except Exception:
            error = payload[:200]
    return ToolTrace(tool=call.name, arguments=call.arguments, ok=ok, error=error)


async def run_agent_loop(
    *,
    task_description: str,
    start_url: str,
    llm_client: LLMClient,
    user_prompt: str | None = None,
    voice: str = "jane",
    browser: str = "chrome",
    language: str = "ru",
    resolution: str = "1920x1080",
    fps: int = 30,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
    iteration_timeout: float = DEFAULT_ITERATION_TIMEOUT,
    tool_timeout: float = DEFAULT_TOOL_TIMEOUT,
    verification_retries: int = DEFAULT_VERIFICATION_RETRIES,
    verification_timeout: float = DEFAULT_VERIFICATION_TIMEOUT,
    headless: bool = True,
    agent_factory=None,
) -> AgentLoopResult:
    """Run the LLM-driven browser exploration loop and return generated YAML.

    The LLM is given function-calling access to a headless Chrome via `BrowserAgent`
    and explores the site itself. Loop terminates on: finish() call, max iterations,
    or wall-clock timeout. On limit hit, the LLM is forced into a final finish()
    call with `exploration_incomplete=true`.

    `agent_factory` is for tests — pass a callable returning a context-manager
    that yields a BrowserAgent-like object.
    """
    started = time.monotonic()
    transcript: list[ToolTrace] = []

    if user_prompt is None:
        user_prompt = build_live_spec_block(
            user_description=task_description,
            start_url=start_url,
            voice=voice,
            browser=browser,
            language=language,
            resolution=resolution,
            fps=fps,
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    factory = agent_factory or (lambda: BrowserAgent(headless=headless))
    verification_attempts = 0
    last_verification: VerificationResult | None = None

    with factory() as agent:
        for iteration in range(1, max_iterations + 1):
            elapsed = time.monotonic() - started
            remaining = total_timeout - elapsed
            if remaining <= 0:
                messages.append(_force_finish_message(f"общий таймаут {total_timeout}s исчерпан"))
                return await _force_finish(
                    llm_client, messages, iteration - 1, transcript, timed_out=True
                )

            log.info("[agent] iter %d/%d (elapsed=%.1fs)", iteration, max_iterations, elapsed)
            try:
                result = await asyncio.wait_for(
                    llm_client.chat_with_tools(messages, TOOL_SCHEMAS),
                    timeout=min(iteration_timeout, remaining),
                )
            except asyncio.TimeoutError:
                log.warning("[agent] LLM call timed out after %.1fs", iteration_timeout)
                messages.append(_force_finish_message("LLM-запрос превысил таймаут"))
                return await _force_finish(
                    llm_client, messages, iteration, transcript, timed_out=True
                )

            if not result.tool_calls:
                messages.append(
                    _force_finish_message(
                        "Ты не вызвал ни одного тула. Используй тулы для исследования или вызови finish()"
                    )
                )
                continue

            messages.append(_assistant_message_from_result(result))

            for call in result.tool_calls:
                if time.monotonic() - started > total_timeout:
                    messages.append(_force_finish_message(f"общий таймаут {total_timeout}s исчерпан между tool calls"))
                    return await _force_finish(
                        llm_client, messages, iteration, transcript, timed_out=True
                    )

                log.info("[agent] tool: %s args=%s", call.name, call.arguments[:120])
                try:
                    tool_result = await asyncio.wait_for(
                        asyncio.to_thread(execute_tool, call.name, call.arguments, agent),
                        timeout=tool_timeout,
                    )
                except asyncio.TimeoutError:
                    err_payload = (
                        f'{{"ok": false, "error": "tool {call.name} exceeded {tool_timeout}s timeout"}}'
                    )
                    log.warning("[agent] tool %s timed out", call.name)
                    transcript.append(_trace_from(call, err_payload))
                    messages.append(_tool_message(call, err_payload))
                    continue

                if isinstance(tool_result, FinishSignal):
                    transcript.append(ToolTrace(tool="finish", arguments=call.arguments, ok=True))

                    if verification_attempts >= verification_retries:
                        log.info("[verify] retries exhausted, accepting YAML as-is")
                        notes = tool_result.notes
                        if last_verification and last_verification.issues:
                            notes = (notes + "\n" if notes else "") + format_issues_for_llm(last_verification)
                        return AgentLoopResult(
                            yaml_script=tool_result.yaml_script,
                            exploration_incomplete=True,
                            iterations=iteration,
                            notes=notes,
                            transcript=transcript,
                            verification_attempts=verification_attempts,
                            verification_passed=False,
                            verification_issues=[
                                f"{iss.scene_path}/{iss.action_path}: {iss.reason}"
                                for iss in (last_verification.issues if last_verification else [])
                            ],
                        )

                    verification_attempts += 1
                    log.info("[verify] attempt %d/%d", verification_attempts, verification_retries + 1)
                    try:
                        last_verification = await asyncio.wait_for(
                            asyncio.to_thread(verify_yaml_by_replay, tool_result.yaml_script, agent),
                            timeout=verification_timeout,
                        )
                    except asyncio.TimeoutError:
                        log.warning("[verify] verification timed out")
                        last_verification = VerificationResult(
                            ok=False, issues=[], selectors_checked=0,
                            yaml_parse_error=f"verification exceeded {verification_timeout}s",
                        )

                    if last_verification.ok:
                        log.info("[verify] PASSED on attempt %d", verification_attempts)
                        return AgentLoopResult(
                            yaml_script=tool_result.yaml_script,
                            exploration_incomplete=tool_result.exploration_incomplete,
                            iterations=iteration,
                            notes=tool_result.notes,
                            transcript=transcript,
                            verification_attempts=verification_attempts,
                            verification_passed=True,
                        )

                    log.warning(
                        "[verify] FAILED on attempt %d: %d issues",
                        verification_attempts,
                        len(last_verification.issues),
                    )
                    issues_text = format_issues_for_llm(last_verification)
                    messages.append(_tool_message(call, f'{{"ok": false, "verification_failed": true, "details": {issues_text!r}}}'))
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Твой finish() ОТКЛОНЁН: при автоматической проверке YAML в живом браузере "
                                "обнаружены ошибки.\n\n" + issues_text +
                                "\n\nИсправь YAML и вызови finish() ещё раз. У тебя осталось "
                                f"{verification_retries - verification_attempts + 1} попыток."
                            ),
                        }
                    )
                    break

                transcript.append(_trace_from(call, tool_result))
                messages.append(_tool_message(call, tool_result))

        messages.append(
            _force_finish_message(f"исчерпан лимит итераций ({max_iterations})")
        )
        return await _force_finish(
            llm_client,
            messages,
            max_iterations,
            transcript,
            hit_iteration_limit=True,
        )


async def _force_finish(
    llm_client: LLMClient,
    messages: list[dict[str, Any]],
    iterations: int,
    transcript: list[ToolTrace],
    *,
    timed_out: bool = False,
    hit_iteration_limit: bool = False,
) -> AgentLoopResult:
    forced_tools = [s for s in TOOL_SCHEMAS if s["function"]["name"] == "finish"]
    try:
        result = await asyncio.wait_for(
            llm_client.chat_with_tools(
                messages,
                forced_tools,
                tool_choice={"type": "function", "function": {"name": "finish"}},
            ),
            timeout=DEFAULT_ITERATION_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("Forced finish() also timed out")
        return AgentLoopResult(
            yaml_script="",
            exploration_incomplete=True,
            iterations=iterations,
            notes="Forced finish timed out — LLM не ответил.",
            transcript=transcript,
            timed_out=True,
            hit_iteration_limit=hit_iteration_limit,
        )

    yaml_script = ""
    notes = ""
    incomplete = True
    for call in result.tool_calls:
        if call.name != "finish":
            continue
        try:
            import json

            args = json.loads(call.arguments)
            yaml_script = args.get("yaml_script", "")
            notes = args.get("notes", "")
            incomplete = bool(args.get("exploration_incomplete", True))
        except json.JSONDecodeError:
            notes = f"Failed to parse finish args: {call.arguments[:200]}"
        break

    return AgentLoopResult(
        yaml_script=yaml_script,
        exploration_incomplete=incomplete,
        iterations=iterations,
        notes=notes,
        transcript=transcript,
        timed_out=timed_out,
        hit_iteration_limit=hit_iteration_limit,
    )
