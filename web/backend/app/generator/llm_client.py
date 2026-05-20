from __future__ import annotations

import logging
from typing import AsyncIterator, List

from openai import AsyncOpenAI

from web.backend.app.generator.config import GeneratorSettings, get_settings

log = logging.getLogger(__name__)


class LLMNotConfiguredError(RuntimeError):
    pass


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
