"""Framework-agnostic callback verification."""

from __future__ import annotations

import hmac
import json
import time
from collections.abc import Callable
from enum import Enum
from urllib.parse import urlsplit

from ..errors import DidwwConfigurationError
from ..secret import decode_secret
from ..signing import sign, string_to_sign

__all__ = ["CallbackVerifier", "RejectionReason", "allow", "deny", "parse_authorization"]

DEFAULT_TOLERANCE = 300


class RejectionReason(Enum):
    """Why a callback failed verification. For your logs, never for your response."""

    MISSING_SIGNATURE = "missing_signature"
    MISSING_TIMESTAMP = "missing_timestamp"
    MALFORMED_TIMESTAMP = "malformed_timestamp"
    STALE_TIMESTAMP = "stale_timestamp"
    BAD_SIGNATURE = "bad_signature"


def parse_authorization(header: str | None) -> tuple[str | None, str | None]:
    """Split ``Application <key>:<signature>`` into its parts.

    Returns ``(None, None)`` for anything else, including the ``Application <key>``
    form, which is the unsigned scheme and carries no signature to check.
    """
    if not header:
        return (None, None)
    scheme, _, credentials = header.partition(" ")
    if scheme != "Application" or not credentials:
        return (None, None)
    key, sep, signature = credentials.partition(":")
    if not sep:
        return (None, None)
    return (key or None, signature or None)


def allow() -> str:
    """The JSON body that lets a verification proceed."""
    return json.dumps({"action": "allow"})


def deny() -> str:
    """The JSON body that denies a verification."""
    return json.dumps({"action": "deny"})


class CallbackVerifier:
    """Checks the signature on an inbound verification callback.

    ``callback_url`` must be the URL **registered with DIDWW**, passed verbatim. The
    service signs that URL's path, not the path the request arrives on, which an
    ingress, a mount prefix or a proxy can change.

    * A registered URL with no path -- ``https://example.com`` -- signs the **empty
      string**, not ``/``.
    * ``https://example.com`` and ``https://example.com/`` are different signatures.
      Do not normalise the trailing slash.

    Answer with :func:`allow` or :func:`deny` and nothing else: a response that says
    *why* it failed is an oracle for which keys exist. There is no retry -- one
    request, one answer, and the verification is decided.
    """

    __slots__ = ("_clock", "_key", "_path", "_tolerance")

    def __init__(
        self,
        *,
        secret: str,
        callback_url: str,
        tolerance: int = DEFAULT_TOLERANCE,
        clock: Callable[[], int] = lambda: int(time.time()),
    ) -> None:
        """
        :param secret: the application secret, same value used for signed requests.
        :param callback_url: the URL registered with DIDWW, verbatim.
        :param tolerance: accepted clock skew in seconds; the service uses 300.
        """
        if tolerance < 0:
            raise DidwwConfigurationError("tolerance must not be negative")
        self._key = decode_secret(secret)
        self._path = self._signed_path(callback_url)
        self._tolerance = tolerance
        self._clock = clock

    @staticmethod
    def _signed_path(callback_url: str) -> str:
        parts = urlsplit(callback_url)
        if not parts.scheme or not parts.netloc:
            raise DidwwConfigurationError(
                f"callback_url must be an absolute URL, got {callback_url!r}"
            )
        return parts.path

    @property
    def signed_path(self) -> str:
        """The path this verifier signs. ``""`` for a registered URL with no path."""
        return self._path

    def check(
        self,
        *,
        method: str,
        content_type: str,
        body: bytes,
        timestamp: str | None,
        signature: str | None,
    ) -> RejectionReason | None:
        """Return ``None`` when the request is authentic, else why it is not.

        ``body`` must be the exact bytes received. Re-serializing parsed parameters
        changes key order, whitespace and escaping, and the signature will not match.
        """
        if not signature:
            return RejectionReason.MISSING_SIGNATURE
        if not timestamp:
            return RejectionReason.MISSING_TIMESTAMP
        try:
            sent_at = int(timestamp)
        except ValueError:
            return RejectionReason.MALFORMED_TIMESTAMP
        if abs(self._clock() - sent_at) > self._tolerance:
            return RejectionReason.STALE_TIMESTAMP

        expected = sign(
            self._key,
            string_to_sign(
                method=method,
                path=self._path,
                content_type=content_type,
                body=body,
                timestamp=timestamp,
            ),
        )
        # Constant time: a short-circuiting compare leaks how much of a forgery matched.
        if not hmac.compare_digest(expected, signature):
            return RejectionReason.BAD_SIGNATURE
        return None

    def is_valid(
        self,
        *,
        method: str,
        content_type: str,
        body: bytes,
        timestamp: str | None,
        signature: str | None,
    ) -> bool:
        """:meth:`check`, as a boolean."""
        return (
            self.check(
                method=method,
                content_type=content_type,
                body=body,
                timestamp=timestamp,
                signature=signature,
            )
            is None
        )
