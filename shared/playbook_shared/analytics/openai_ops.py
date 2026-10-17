"""OpenAI calls used by analytics.

All functions are narrow and injectable from tests so normal CI never needs
network or an API key.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

from openai import OpenAI

from playbook_shared.analytics.models import EMBEDDING_DIM

_client: OpenAI | None = None
DEFAULT_REQUEST_TIMEOUT_SECONDS = 45.0


def get_client() -> OpenAI:
    global _client
    if _client is None:
        base_url = os.environ.get("OPENAI_BASE_URL")
        _client = OpenAI(base_url=base_url) if base_url else OpenAI()
    return _client


def request_timeout_seconds() -> float:
    value = os.environ.get("OPENAI_REQUEST_TIMEOUT_SECONDS")
    if value is None:
        return DEFAULT_REQUEST_TIMEOUT_SECONDS
    try:
        timeout = float(value)
    except ValueError as exc:
        raise ValueError("OPENAI_REQUEST_TIMEOUT_SECONDS must be a number") from exc
    if timeout <= 0:
        raise ValueError("OPENAI_REQUEST_TIMEOUT_SECONDS must be greater than 0")
    return timeout


def request_client() -> OpenAI:
    return get_client().with_options(timeout=request_timeout_seconds())


def synthetic_model() -> str:
    return os.environ.get("OPENAI_SYNTHETIC_MODEL", "gpt-4o-mini")


def fallback_synthetic_model() -> str:
    return os.environ.get("OPENAI_SYNTHETIC_FALLBACK_MODEL", "gpt-4.1-mini")


def embedding_model() -> str:
    return os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def embed_texts(texts: Sequence[str], model: str | None = None) -> list[list[float]]:
    if not texts:
        return []
    resp = request_client().embeddings.create(model=model or embedding_model(), input=list(texts))
    vectors = [item.embedding for item in resp.data]
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(f"embedding dimension {len(vector)} != {EMBEDDING_DIM}")
    return vectors


def generate_answers(prompt: str, slot_keys: Sequence[str], model: str | None = None) -> dict[str, str]:
    """Generate one respondent's answer map keyed by slot_key."""
    resp = request_client().chat.completions.create(
        model=model or synthetic_model(),
        messages=[
            {
                "role": "system",
                "content": (
                    "Return only JSON. Generate realistic first-person finance discovery "
                    "answers for the requested slot keys. Use every exact slot key."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    parsed: dict[str, Any] = json.loads(content)
    return {key: str(parsed.get(key, "")).strip() for key in slot_keys}


def labeling_model() -> str:
    return os.environ.get("OPENAI_LABELING_MODEL", "gpt-4o-mini")


def label_cluster(prompt: str, model: str | None = None) -> dict[str, Any]:
    resp = request_client().chat.completions.create(
        model=model or labeling_model(),
        messages=[
            {
                "role": "system",
                "content": "Return only JSON with exactly the fields the prompt requests.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content or "{}")
