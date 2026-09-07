"""Phone-number handling for the ``by_number`` paths."""

from __future__ import annotations

import re

from .errors import DidwwConfigurationError

__all__ = ["digits_of"]

_NON_DIGIT = re.compile(r"\D")


def digits_of(number: str) -> str:
    """Reduce ``number`` to ASCII digits for use as a single URL path segment.

    The service strips every non-digit before a lookup, so nothing is lost. Percent-
    encoding instead leaves ``.`` untouched, and a dotted ``+371.12345678`` then has
    its tail read as a format suffix and 404s on a number that exists.
    """
    digits = _NON_DIGIT.sub("", number)
    if not digits:
        raise DidwwConfigurationError(f"Phone number contains no digits: {number!r}")
    return digits
