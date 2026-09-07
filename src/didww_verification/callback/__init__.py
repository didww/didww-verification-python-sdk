"""Verification of inbound callbacks.

Before creating a verification, the API can call your registered callback URL and wait
for you to allow or deny it. This module checks that such a request really came from
DIDWW.

Free of any HTTP client: importing :class:`CallbackVerifier` pulls in nothing but the
standard library and this package's signing code.
"""

from ._verifier import CallbackVerifier, RejectionReason, allow, deny, parse_authorization

__all__ = ["CallbackVerifier", "RejectionReason", "allow", "deny", "parse_authorization"]
