"""HMAC-SHA256 request signing, shared by outbound requests and inbound callbacks.

Pure: no HTTP client, no clock, no I/O.

The string to sign is exactly five lines joined by ``\\n``, with no trailing
newline::

    <HTTP-METHOD>
    <CONTENT-MD5>
    <CONTENT-TYPE>
    x-timestamp:<TIMESTAMP>
    <PATH>
"""

from __future__ import annotations

import base64
import hashlib
import hmac

__all__ = ["sign", "string_to_sign"]


def _content_md5(body: bytes | None) -> str:
    """Base64 of MD5 over the body, or ``""`` when there is effectively no body.

    A whitespace-only body counts as *no* body: the service tests for presence, not
    emptiness, so signing the MD5 of the whitespace instead yields a 401.
    """
    if body is None or not body.strip():
        return ""
    return base64.b64encode(hashlib.md5(body).digest()).decode("ascii")


def string_to_sign(
    *,
    method: str,
    path: str,
    content_type: str,
    body: bytes | None,
    timestamp: int | str,
) -> bytes:
    """Build the canonical five-line string.

    ``path`` must be the request-target path as it appears in the request line:
    percent-encoding intact, query removed. ``content_type`` is the header value
    actually sent, or ``""`` when no ``Content-Type`` header is sent at all -- the
    required shape for a bodyless request.

    Exposed separately from :func:`sign` so a mismatch can be diffed against the service.
    """
    lines = (
        method.upper(),
        _content_md5(body),
        content_type,
        f"x-timestamp:{timestamp}",
        path,
    )
    return "\n".join(lines).encode("utf-8")


def sign(key: bytes, sts: bytes) -> str:
    """Return the base64 signature of ``sts`` under ``key``.

    ``key`` is the *decoded* secret; see :func:`didww_verification.secret.decode_secret`.
    """
    return base64.b64encode(hmac.new(key, sts, hashlib.sha256).digest()).decode("ascii")
