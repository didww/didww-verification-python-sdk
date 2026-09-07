"""The three authentication schemes, as a closed union.

Separate types rather than a mode string plus an optional secret, so the pairing is a
type error: :class:`PublicAuth` has nowhere to put a secret, and the other two cannot
be built without one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from .secret import decode_secret

__all__ = ["ApplicationAuth", "Auth", "BasicAuth", "PublicAuth"]


@dataclass(frozen=True, slots=True)
class PublicAuth:
    """``Authorization: Application <key>``. No secret.

    The key identifies, it does not authenticate, so it is safe in a client users can
    read. What authorises a start is the application's registered callback URL; with
    none registered, a start under this scheme is denied.
    """

    key: str


@dataclass(frozen=True, slots=True)
class BasicAuth:
    """``Authorization: Basic base64(key:secret)``.

    Server-to-server only -- the secret is recoverable from anything that ships it.
    """

    key: str
    secret: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ApplicationAuth:
    """Per-request HMAC signature plus an ``x-timestamp`` header.

    The strongest scheme, and the only one whose starts skip the outbound callback.
    The secret is validated eagerly by :meth:`key_bytes`, so a malformed one fails at
    construction rather than as a 401 on the first request.
    """

    key: str
    secret: str = field(repr=False)

    def key_bytes(self) -> bytes:
        """The raw HMAC key. Raises ``DidwwConfigurationError`` if the secret is unusable."""
        return decode_secret(self.secret)


Auth: TypeAlias = PublicAuth | BasicAuth | ApplicationAuth
