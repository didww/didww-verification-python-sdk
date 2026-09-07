"""Decoding of the application secret into the raw HMAC key."""

from __future__ import annotations

import base64
import binascii
import re

from .errors import DidwwConfigurationError

__all__ = ["decode_secret"]

_ALPHABET = re.compile(r"[A-Za-z0-9_+/-]+")
_URLSAFE_TO_STD = str.maketrans("-_", "+/")


def decode_secret(secret: str) -> bytes:
    """Return the raw HMAC key for ``secret``: its decoded *bytes*, never its characters.

    Padding is optional and a non-canonical final quantum is accepted, matching the
    service -- ``..._AA``, ``..._AB`` and ``..._AC`` decode to the same key. Rejected is
    input that cannot be a secret at all (a stray space from a wrapped config value, an
    en-dash, an impossible length). Unguarded, most of those raise deep inside base64
    at the first signed request; an empty one signs with an empty key.
    """
    body = secret.rstrip("=")
    if not body:
        raise DidwwConfigurationError("Application secret is empty.")
    if not _ALPHABET.fullmatch(body):
        raise DidwwConfigurationError(
            "Application secret is not base64 -- it contains a character outside the "
            "base64 alphabet (a stray space, newline, or a dash pasted as an en-dash)."
        )
    if len(body) % 4 == 1:
        raise DidwwConfigurationError("Application secret is not a valid base64 length.")
    padded = body.translate(_URLSAFE_TO_STD) + "=" * (-len(body) % 4)
    try:
        return base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError) as exc:  # pragma: no cover - guarded above
        raise DidwwConfigurationError(f"Application secret is not base64: {exc}") from exc
