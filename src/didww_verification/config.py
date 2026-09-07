"""Client configuration."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlsplit

from ._version import VERSION
from .errors import DidwwConfigurationError

__all__ = ["DEFAULT_USER_AGENT", "Environment", "RetryPolicy", "validate_base_url"]

DEFAULT_USER_AGENT = f"didww-verification-python/{VERSION}"


class Environment(Enum):
    """The environments the API publishes."""

    PRODUCTION = "https://verification.didww.com"
    SANDBOX = "https://verification-sandbox.didww.com"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How often to retry a *read*, and how long to wait.

    ``attempts`` counts total tries, so the default of 2 means one retry. Only reads
    are ever retried; see :func:`didww_verification._retry.is_retryable`.
    """

    attempts: int = 2
    base_delay: float = 0.2
    clock: Callable[[], int] = field(default=lambda: int(time.time()), repr=False)
    """Unix seconds, for the request timestamp. Injected so signatures are
    reproducible in tests."""
    rand: Callable[[], float] = field(default=random.random, repr=False)
    """Jitter source. Injected so backoff is reproducible in tests."""

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise DidwwConfigurationError("retry attempts must be at least 1")
        if self.base_delay < 0:
            raise DidwwConfigurationError("retry base_delay must not be negative")


def validate_base_url(base_url: str) -> str:
    """Check that ``base_url`` is an origin, and return it without a trailing slash.

    A path is rejected rather than accommodated: the SDK appends its own ``/api/v1``,
    so a base URL that already carries it doubles the path and 404s as if the
    verification were missing.
    """
    parts = urlsplit(base_url)
    if not parts.scheme or not parts.netloc:
        raise DidwwConfigurationError(f"base_url must be an absolute URL, got {base_url!r}")
    if parts.path not in ("", "/"):
        raise DidwwConfigurationError(
            f"base_url must be an origin with no path, got {base_url!r}. "
            "The API prefix is added by this SDK."
        )
    if parts.query or parts.fragment:
        raise DidwwConfigurationError(f"base_url must carry no query or fragment, got {base_url!r}")
    return f"{parts.scheme}://{parts.netloc}"
