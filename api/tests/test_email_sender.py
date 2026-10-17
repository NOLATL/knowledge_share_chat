"""Unit tests for the Resend HTTP path (no network)."""

from __future__ import annotations

import io
from urllib import error, request

from api import email_sender


def test_resend_request_sets_explicit_user_agent(monkeypatch):
    """Cloudflare bans urllib's default UA (error 1010); we must always send our own."""
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout):
        captured["ua"] = req.headers.get("User-agent", "")
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    result = email_sender._send_resend(
        api_key="k",
        to_email="peer@example.com",
        relay_url="https://web.example/relay/t",
        question_text="How long is close?",
    )
    assert result.delivered is True
    assert captured["ua"] == "playbook-relay/1.0"


def test_resend_non_json_error_body_is_surfaced(monkeypatch):
    def fake_urlopen(req, timeout):
        raise error.HTTPError(
            req.full_url, 403, "Forbidden", {}, io.BytesIO(b"error code: 1010\n")
        )

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    result = email_sender._send_resend(
        api_key="k",
        to_email="peer@example.com",
        relay_url="https://web.example/relay/t",
        question_text="How long is close?",
    )
    assert result.delivered is False
    assert result.message == "HTTP 403: error code: 1010"
