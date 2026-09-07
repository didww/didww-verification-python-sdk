from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from didww_verification.config import RetryPolicy

FIXED_TIMESTAMP = 1700000000
SECRET = "tEsT_secret_urlsafe_base64_value_AA"


@pytest.fixture
def fixed_retry() -> RetryPolicy:
    """Deterministic clock and jitter, so signatures and backoff are reproducible."""
    return RetryPolicy(attempts=2, base_delay=0.0, clock=lambda: FIXED_TIMESTAMP, rand=lambda: 0.0)


def verification_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "9f1c0a5e-0000-4000-8000-000000000001",
        "destination": "37112345678",
        "delivery_method": "sms",
        "fee": "0.0450",
        "status": "pending",
        "error_code": None,
        "error_detail": None,
        # A trailing Z, as the service sends: unreadable by fromisoformat before 3.11.
        "expires_at": "2026-09-03T12:00:00Z",
        "sms": {
            "template": "Your code is {{CODE}}",
            "language": "en-US",
            "interception_timeout": 120,
        },
    }
    data.update(overrides)
    return data


def recording_transport(
    status: int = 200, payload: dict[str, Any] | None = None, body: bytes | None = None
) -> tuple[httpx2.MockTransport, list[httpx2.Request]]:
    """A transport that records the fully built request and replies with a canned response.

    Asserting on the recorded request is the point: it is the only way to see what
    actually goes on the wire, including headers a client default may have added.
    """
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if body is not None:
            return httpx2.Response(status, content=body)
        body_text = json.dumps({"data": payload or verification_payload()})
        return httpx2.Response(status, content=body_text)

    return httpx2.MockTransport(handler), seen
