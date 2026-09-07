"""Everything this SDK raises.

Outcomes are not errors: a verification that ends ``failed``, ``expired`` or ``denied``
arrives as a normal 200. Only a non-2xx, a transport fault, or a malformed payload
raises.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DidwwApiError",
    "DidwwBalanceInsufficientError",
    "DidwwConfigurationError",
    "DidwwDecodingError",
    "DidwwNotFoundError",
    "DidwwServerError",
    "DidwwTransportError",
    "DidwwUnauthorizedError",
    "DidwwValidationError",
    "DidwwVerificationError",
    "ErrorItem",
]


class DidwwVerificationError(Exception):
    """Base class for every error this SDK raises."""


class DidwwConfigurationError(DidwwVerificationError):
    """The client was built wrong: a bad secret, an unusable base URL."""


class DidwwTransportError(DidwwVerificationError):
    """The request never produced an HTTP response.

    Every underlying HTTP-library error is converted to this, so the HTTP library
    never appears in a caller's ``except`` and can be replaced without breaking one.
    """


class DidwwDecodingError(DidwwVerificationError):
    """A 2xx response did not carry a verification this SDK could read.

    Never raised for a non-2xx: those map to :class:`DidwwApiError` even when the body
    is not JSON, so a proxy's error page is reported as the server error it is.
    """

    def __init__(self, message: str, *, body: str | None = None) -> None:
        super().__init__(message)
        self.body = body


@dataclass(frozen=True, slots=True)
class ErrorItem:
    """One coded error from the API's ``{"errors": [...]}`` envelope.

    ``code`` is a stable slug -- switch on it. ``detail`` is fixed prose chosen by
    the code, not per-request text; show it, never parse it.
    """

    code: str | None
    detail: str | None

    def __str__(self) -> str:
        return self.detail or self.code or ""


class DidwwApiError(DidwwVerificationError):
    """A non-2xx response.

    One response can carry several errors -- a validation failure returns one per
    field -- so :attr:`codes` is the reliable accessor, not ``errors[0]``.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        status: int,
        errors: tuple[ErrorItem, ...] = (),
        body: str | None = None,
    ) -> None:
        details = [e.detail for e in errors if e.detail]
        super().__init__(message or (", ".join(details) if details else f"HTTP {status}"))
        self.status = status
        self.errors = errors
        self.body = body

    @property
    def codes(self) -> tuple[str, ...]:
        """Every code in the envelope, in order."""
        return tuple(e.code for e in self.errors if e.code is not None)

    def has_code(self, code: str) -> bool:
        """True when the envelope carries ``code`` anywhere."""
        return code in self.codes


class DidwwUnauthorizedError(DidwwApiError):
    """401. Covers every rejection -- unknown key, bad signature, stale timestamp,
    a scheme below the application's minimum -- with no further detail by design."""


class DidwwBalanceInsufficientError(DidwwApiError):
    """402."""


class DidwwNotFoundError(DidwwApiError):
    """404. Also what a finished verification becomes once it is past retention."""


class DidwwValidationError(DidwwApiError):
    """400 or 422."""


class DidwwServerError(DidwwApiError):
    """5xx, including an error produced by infrastructure in front of the API."""
