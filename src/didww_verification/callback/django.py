"""Callback verification for Django.

Import only where you use it -- Django is not a dependency of this package::

    from didww_verification.callback import allow, deny
    from didww_verification.callback.django import verify_request

    verifier = CallbackVerifier(secret=SECRET, callback_url="https://example.com/didww")

    @csrf_exempt
    def callback(request):
        if not verify_request(verifier, request):
            return HttpResponse(status=401)
        return HttpResponse(allow(), content_type="application/json")

The view must be exempt from CSRF: the request comes from DIDWW, not from a form,
and carries its own signature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._verifier import CallbackVerifier, RejectionReason, parse_authorization

if TYPE_CHECKING:
    from django.http import HttpRequest

__all__ = ["check_request", "verify_request"]


def check_request(verifier: CallbackVerifier, request: HttpRequest) -> RejectionReason | None:
    """Verify a Django request. ``None`` means authentic.

    Reads ``request.body`` -- the received bytes. Touching ``request.POST`` first
    consumes the stream and makes the body unavailable, so verify before parsing.
    """
    _key, signature = parse_authorization(request.headers.get("Authorization"))
    return verifier.check(
        method=request.method or "",
        content_type=request.headers.get("Content-Type", ""),
        body=request.body,
        timestamp=request.headers.get("x-timestamp"),
        signature=signature,
    )


def verify_request(verifier: CallbackVerifier, request: HttpRequest) -> bool:
    """:func:`check_request`, as a boolean."""
    return check_request(verifier, request) is None
