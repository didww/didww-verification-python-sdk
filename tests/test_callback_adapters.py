"""The FastAPI/Starlette and Django adapters.

Both are thin, and the thing worth proving is the same for each: they read the raw
received bytes. Re-serializing parsed parameters changes key order, whitespace and
unicode escaping, and the signature then never matches.

The request objects are built directly rather than through a test client, so these
exercise the adapter and nothing else.
"""

from __future__ import annotations

import json

import anyio

from didww_verification.callback import CallbackVerifier, RejectionReason
from didww_verification.callback.django import check_request as django_check
from didww_verification.callback.fastapi import check_request as starlette_check
from didww_verification.secret import decode_secret
from didww_verification.signing import sign, string_to_sign
from tests.conftest import SECRET

NOW = 1700000000
PATH = "/callbacks/didww"
BODY = json.dumps(
    {
        "event": "verification_request",
        "data": {"id": "abc", "destination": "37112345678", "delivery_method": "sms"},
    }
).encode()


def verifier() -> CallbackVerifier:
    return CallbackVerifier(
        secret=SECRET, callback_url=f"https://example.com{PATH}", clock=lambda: NOW
    )


def good_signature(body: bytes = BODY) -> str:
    return sign(
        decode_secret(SECRET),
        string_to_sign(
            method="POST",
            path=PATH,
            content_type="application/json",
            body=body,
            timestamp=NOW,
        ),
    )


def _headers(signature: str | None, timestamp: str | None = str(NOW)) -> list[tuple[bytes, bytes]]:
    out = [(b"content-type", b"application/json")]
    if signature is not None:
        out.append((b"authorization", f"Application key:{signature}".encode()))
    if timestamp is not None:
        out.append((b"x-timestamp", timestamp.encode()))
    return out


class TestStarlette:
    def _request(self, signature: str | None, body: bytes = BODY) -> object:
        from starlette.requests import Request

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": PATH,
            "raw_path": PATH.encode(),
            "query_string": b"",
            "headers": _headers(signature),
            "scheme": "https",
            "server": ("example.com", 443),
            "client": ("192.0.2.1", 1234),  # RFC 5737 documentation range
        }
        received = [
            {"type": "http.request", "body": body, "more_body": False},
        ]

        async def receive() -> dict[str, object]:
            return received.pop(0)

        return Request(scope, receive)

    def test_a_valid_callback_passes(self) -> None:
        request = self._request(good_signature())
        assert anyio.run(lambda: starlette_check(verifier(), request)) is None  # type: ignore[arg-type]

    def test_a_tampered_body_fails(self) -> None:
        request = self._request(good_signature(), body=BODY + b" ")
        got = anyio.run(lambda: starlette_check(verifier(), request))  # type: ignore[arg-type]
        assert got is RejectionReason.BAD_SIGNATURE

    def test_a_missing_signature_fails(self) -> None:
        request = self._request(None)
        got = anyio.run(lambda: starlette_check(verifier(), request))  # type: ignore[arg-type]
        assert got is RejectionReason.MISSING_SIGNATURE


class TestDjango:
    def _request(self, signature: str | None, body: bytes = BODY) -> object:
        import django
        from django.conf import settings

        if not settings.configured:
            settings.configure(DEBUG=True, ALLOWED_HOSTS=["*"], USE_TZ=True)
            django.setup()

        from django.test import RequestFactory

        authorization = "" if signature is None else f"Application key:{signature}"
        return RequestFactory().post(
            PATH,
            data=body,
            content_type="application/json",
            HTTP_AUTHORIZATION=authorization,
            HTTP_X_TIMESTAMP=str(NOW),
        )

    def test_a_valid_callback_passes(self) -> None:
        assert django_check(verifier(), self._request(good_signature())) is None  # type: ignore[arg-type]

    def test_a_tampered_body_fails(self) -> None:
        request = self._request(good_signature(), body=BODY + b" ")
        assert django_check(verifier(), request) is RejectionReason.BAD_SIGNATURE  # type: ignore[arg-type]

    def test_a_missing_signature_fails(self) -> None:
        request = self._request(None)
        assert django_check(verifier(), request) is RejectionReason.MISSING_SIGNATURE  # type: ignore[arg-type]
