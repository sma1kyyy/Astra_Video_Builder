from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from web.backend.app.generator.browser_agent import (
    AgentObservation,
    BrowserAgent,
    BrowserAgentError,
)

log = logging.getLogger(__name__)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": (
                "Открыть URL в браузере. Используй для первого захода и для прямых "
                "переходов по известному адресу. Возвращает новый URL, title и компактное "
                "представление DOM с интерактивными элементами."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Полный URL включая https://"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": (
                "Клик по элементу. Селектор — CSS (по умолчанию) или XPath (если "
                "начинается с / или с (). Используй РЕАЛЬНЫЕ селекторы из последнего "
                "DOM-листинга, не выдумывай."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": (
                "Ввести текст в поле ввода. Опционально нажать Enter после ввода "
                "(submit=true) — полезно для поисковых форм."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "submit": {"type": "boolean", "default": False},
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Прокрутить страницу. direction: up|down|top|bottom.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "top", "bottom"]},
                    "pixels": {"type": "integer", "default": 500},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Подождать N секунд (0–10) для асинхронной загрузки. Возвращает текущее состояние DOM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "minimum": 0, "maximum": 10},
                },
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "observe",
            "description": "Принудительный пересняв DOM без действия. Используй редко — навигационные тулы уже возвращают DOM.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "Завершить исследование и вернуть итоговый YAML-скрипт. Вызывай "
                "ТОЛЬКО когда полностью убедился в правильности всех селекторов и "
                "понял весь путь пользователя. Если данных не хватило — установи "
                "exploration_incomplete=true и отдай минимальный рабочий MVP."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "yaml_script": {
                        "type": "string",
                        "description": "Полный YAML согласно спецификации live mode",
                    },
                    "exploration_incomplete": {"type": "boolean", "default": False},
                    "notes": {
                        "type": "string",
                        "description": "Опциональные заметки об упрощениях/ограничениях",
                    },
                },
                "required": ["yaml_script"],
            },
        },
    },
]


@dataclass
class FinishSignal:
    yaml_script: str
    exploration_incomplete: bool = False
    notes: str = ""


def _observation_to_payload(obs: AgentObservation) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "url": obs.url,
        "title": obs.title,
        "dom": obs.dom,
        "dom_truncated": obs.truncated,
        "element_count": obs.element_count,
        "likely_unrendered": obs.likely_unrendered,
    }
    if obs.note:
        payload["note"] = obs.note
    return payload


def _error_payload(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def execute_tool(name: str, arguments: str, agent: BrowserAgent) -> str | FinishSignal:
    """Dispatch an LLM tool call to the browser agent.

    Returns a JSON string with the result (for `role=tool` messages) OR a
    `FinishSignal` instance when the LLM calls `finish` — the caller must
    terminate the loop in that case.
    """
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return json.dumps(_error_payload(exc), ensure_ascii=False)

    if name == "finish":
        return FinishSignal(
            yaml_script=args.get("yaml_script", ""),
            exploration_incomplete=bool(args.get("exploration_incomplete", False)),
            notes=args.get("notes", ""),
        )

    try:
        if name == "navigate":
            obs = agent.navigate(args["url"])
        elif name == "click":
            obs = agent.click(args["selector"])
        elif name == "type_text":
            obs = agent.type_text(
                args["selector"],
                args["text"],
                submit=bool(args.get("submit", False)),
            )
        elif name == "scroll":
            obs = agent.scroll(args["direction"], int(args.get("pixels", 500)))
        elif name == "wait":
            seconds = float(args.get("seconds", 1.0))
            agent.wait(seconds)
            obs = agent.observe(extra_delay=0.0)
        elif name == "observe":
            obs = agent.observe()
        else:
            return json.dumps(
                {"ok": False, "error": f"unknown tool: {name}"}, ensure_ascii=False
            )
    except KeyError as exc:
        return json.dumps(
            {"ok": False, "error": f"missing argument: {exc}"}, ensure_ascii=False
        )
    except BrowserAgentError as exc:
        return json.dumps(_error_payload(exc), ensure_ascii=False)
    except Exception as exc:
        log.exception("Unexpected tool error in %s", name)
        return json.dumps(_error_payload(exc), ensure_ascii=False)

    return json.dumps(_observation_to_payload(obs), ensure_ascii=False)
