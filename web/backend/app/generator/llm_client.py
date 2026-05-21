from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, List

from openai import AsyncOpenAI

from web.backend.app.generator.config import GeneratorSettings, get_settings

log = logging.getLogger(__name__)


class LLMNotConfiguredError(RuntimeError):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class ToolChatResult:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None


def _merge_choices(response: Any) -> ToolChatResult:
    """Merge multi-choice tool responses from non-OpenAI providers.

    Some Claude-via-OpenAI proxies return text and tool_calls in SEPARATE
    choices, not in one message like the OpenAI spec. We merge them so the
    rest of the codebase sees a single coherent message.
    """
    parts: list[str] = []
    calls: list[ToolCall] = []
    finish: str | None = None
    for ch in response.choices or []:
        if ch.finish_reason and finish is None:
            finish = ch.finish_reason
        msg = ch.message
        if msg.content:
            parts.append(msg.content)
        for tc in msg.tool_calls or []:
            calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
            )
    return ToolChatResult(
        content="\n".join(parts) if parts else None,
        tool_calls=calls,
        finish_reason=finish,
    )


class LLMClient:
    def __init__(self, settings: GeneratorSettings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.is_configured:
            raise LLMNotConfiguredError("LLM_API_KEY is empty; configure .env first")
        self._client = AsyncOpenAI(
            api_key=self._settings.llm_api_key,
            base_url=self._settings.llm_base_url,
            default_headers={
                "User-Agent": "aa-video-builder/0.1",
                "Connection": "keep-alive",
            },
        )

    @property
    def model(self) -> str:
        return self._settings.llm_model

    @property
    def raw(self) -> AsyncOpenAI:
        return self._client

    async def complete(self, messages: List[dict], *, temperature: float = 0.2) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def stream(self, messages: List[dict], *, temperature: float = 0.2) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    async def chat_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
        *,
        temperature: float = 0.2,
        tool_choice: str = "auto",
    ) -> ToolChatResult:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
        )
        return _merge_choices(response)
