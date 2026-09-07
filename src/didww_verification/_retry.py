"""Retry decisions. Pure: decides whether and how long, never sleeps."""

from __future__ import annotations

from ._responses import Outcome, TransportFailure

__all__ = ["delay_for", "is_retryable"]


def is_retryable(outcome: Outcome) -> bool:
    """True for a transport fault or a 5xx, and nothing else.

    Which *requests* may be retried at all is the caller's decision: only reads are,
    because a repeated start supersedes the live verification and charges again, and a
    repeated report consumes an attempt.
    """
    if isinstance(outcome, TransportFailure):
        return True
    return outcome.status >= 500


def delay_for(attempt: int, base_delay: float, random_value: float) -> float:
    """Exponential backoff with full jitter, in seconds.

    ``random_value`` is supplied rather than drawn so the schedule is reproducible.
    """
    return float(base_delay * (2 ** (attempt - 1)) * random_value)
