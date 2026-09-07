"""Callback verification for FastAPI and Starlette.

Import only where you use it -- Starlette is not a dependency of this package::

    from didww_verification.callback import allow, deny
    from didww_verification.callback.fastapi import verify_request

    verifier = CallbackVerifier(secret=SECRET, callback_url="https://example.com/didww")

    @app.post("/didww")
    async def callback(request: Request) -> Response:
        if not await verify_request(verifier, request):
            return Response(status_code=401)
        payload = await request.json()
        return Response(allow(), media_type="application/json")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._verifier import CallbackVerifier, RejectionReason, parse_authorization

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = ["check_request", "verify_request"]


async def check_request(verifier: CallbackVerifier, request: Request) -> RejectionReason | None:
    """Verify a Starlette/FastAPI request. ``None`` means authentic.

    Reads ``await request.body()`` -- the received bytes -- rather than parsed
    parameters, which would not re-serialize identically.
    """
    _key, signature = parse_authorization(request.headers.get("authorization"))
    return verifier.check(
        method=request.method,
        content_type=request.headers.get("content-type", ""),
        body=await request.body(),
        timestamp=request.headers.get("x-timestamp"),
        signature=signature,
    )


async def verify_request(verifier: CallbackVerifier, request: Request) -> bool:
    """:func:`check_request`, as a boolean."""
    return await check_request(verifier, request) is None
