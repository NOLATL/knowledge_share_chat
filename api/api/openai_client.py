"""OpenAI client + streamed chat call (the two-call pattern's call A).

This module owns ONLY the streamed natural-language reply (GR2). The separate,
non-streamed Structured Outputs extraction call is Task 1.3 and lives elsewhere.

`stream_chat` is the single seam the chat route depends on; tests monkeypatch it
so the suite runs with no network / no API key.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from playbook_shared.extraction_schemas import TurnExtraction

CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "gpt-5.4-mini")
EXTRACTION_MODEL = os.environ.get("OPENAI_EXTRACTION_MODEL", "gpt-5.4")
REPORT_MODEL = os.environ.get("OPENAI_REPORT_MODEL", "gpt-5.4-mini")

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Lazily build the client (reads OPENAI_API_KEY / OPENAI_BASE_URL from env)."""
    global _client
    if _client is None:
        base_url = os.environ.get("OPENAI_BASE_URL")
        _client = AsyncOpenAI(base_url=base_url) if base_url else AsyncOpenAI()
    return _client


async def stream_chat(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Stream the assistant reply token-by-token for the given chat messages."""
    stream = await get_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        stream=True,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def complete_chat(messages: list[dict[str, str]]) -> str:
    """Non-streamed chat completion (used for the generated session intro)."""
    resp = await get_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        stream=False,
    )
    return resp.choices[0].message.content or ""


async def parse_extraction(messages: list[dict[str, str]]) -> TurnExtraction:
    """Non-streamed Structured Outputs call (call B) — strict schema, no tools.

    The SDK derives a `strict: true` JSON schema from the Pydantic model; because
    this uses `response_format` (not function tools) there are no parallel tool
    calls to disable (GR4).
    """
    resp = await get_client().beta.chat.completions.parse(
        model=EXTRACTION_MODEL,
        messages=messages,
        response_format=TurnExtraction,
    )
    parsed = resp.choices[0].message.parsed
    return parsed if parsed is not None else TurnExtraction(extractions=[])


async def complete_report(messages: list[dict[str, str]]) -> str:
    """Non-streamed report generation call, separate from chat and extraction."""
    resp = await get_client().chat.completions.create(
        model=REPORT_MODEL,
        messages=messages,
        stream=False,
    )
    return resp.choices[0].message.content or ""
