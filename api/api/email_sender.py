"""Outbound email helpers for tokenized colleague relay links."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from urllib import error, request

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailResult:
    delivered: bool
    provider: str
    message: str


def relay_base_url() -> str:
    return (
        os.environ.get("RELAY_BASE_URL")
        or os.environ.get("PUBLIC_WEB_BASE_URL")
        or "http://localhost:3000"
    ).rstrip("/")


def send_relay_email(*, to_email: str, relay_url: str, question_text: str, context_text: str = "") -> EmailResult:
    """Send a relay email when Resend is configured; otherwise log the link."""
    api_key = os.environ.get("RESEND_API_KEY")
    if api_key:
        return _send_resend(
            api_key=api_key,
            to_email=to_email,
            relay_url=relay_url,
            question_text=question_text,
            context_text=context_text,
        )

    logger.info("relay email dry-run to %s: %s", to_email, relay_url)
    return EmailResult(delivered=False, provider="log", message="RESEND_API_KEY not set; relay URL returned")


def _send_resend(*, api_key: str, to_email: str, relay_url: str, question_text: str, context_text: str = "") -> EmailResult:
    from_email = os.environ.get("EMAIL_FROM", "Playbook <onboarding@resend.dev>")
    context_block = f"{context_text}\n\n" if context_text.strip() else ""
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": "Input requested for a Playbook discovery question",
        "text": (
            "A colleague requested your input for this discovery question:\n\n"
            f"{question_text}\n\n"
            f"{context_block}"
            f"Reply here: {relay_url}\n\n"
            "This link is single-use and expires automatically."
        ),
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "https://api.resend.com/emails",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Cloudflare in front of api.resend.com bans urllib's default
            # Python-urllib UA (error 1010) — any explicit UA passes.
            "User-Agent": "playbook-relay/1.0",
        },
    )
    try:
        with request.urlopen(req, timeout=12) as response:
            if 200 <= response.status < 300:
                return EmailResult(delivered=True, provider="resend", message="sent")
            return EmailResult(delivered=False, provider="resend", message=f"HTTP {response.status}")
    except error.HTTPError as exc:
        # Resend's error body names the actual reason (e.g. sandbox recipient
        # restriction) — surface it instead of a bare status code.
        raw = ""
        detail = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            body = json.loads(raw)
            detail = body.get("message") or body.get("error") or ""
        except Exception:  # noqa: BLE001 - body may be empty or non-JSON (e.g. a CDN block page)
            detail = raw[:200].strip()
        message = f"HTTP {exc.code}: {detail}" if detail else f"HTTP {exc.code}: {exc.reason}"
        logger.error("resend relay email failed: %s", message)
        return EmailResult(delivered=False, provider="resend", message=message)
    except Exception as exc:  # noqa: BLE001 - outbound email failure should be reported cleanly
        logger.exception("resend relay email failed")
        return EmailResult(delivered=False, provider="resend", message=str(exc))
