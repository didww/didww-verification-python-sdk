"""Strict ISO 8601 parsing for timestamps the API returns.

Not ``datetime.fromisoformat``: before Python 3.11 it cannot read the trailing ``Z``
the API emits, and 3.10 is this package's floor.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

__all__ = ["parse_timestamp"]

_ISO8601 = re.compile(
    r"""
    ^
    (?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})
    [Tt ]
    (?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})
    (?:\.(?P<fraction>\d{1,9}))?
    (?:
        (?P<utc>[Zz])
      | (?P<sign>[+-])(?P<offset_h>\d{2}):?(?P<offset_m>\d{2})
    )?
    $
    """,
    re.VERBOSE,
)


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp.

    Accepts a trailing ``Z``, an offset with or without a colon, and a fractional
    second up to nanoseconds (truncated to microseconds). No offset means UTC.

    Raises ``ValueError`` on anything else, ``2026-02-30`` included.
    """
    match = _ISO8601.match(value)
    if match is None:
        raise ValueError(f"not an ISO 8601 timestamp: {value!r}")

    parts = match.groupdict()
    fraction = parts["fraction"] or ""
    microsecond = int(fraction.ljust(6, "0")[:6]) if fraction else 0

    if parts["sign"] is not None:
        delta = timedelta(hours=int(parts["offset_h"]), minutes=int(parts["offset_m"]))
        tz = timezone(-delta if parts["sign"] == "-" else delta)
    else:
        tz = timezone.utc

    return datetime(
        int(parts["year"]),
        int(parts["month"]),
        int(parts["day"]),
        int(parts["hour"]),
        int(parts["minute"]),
        int(parts["second"]),
        microsecond,
        tzinfo=tz,
    )
