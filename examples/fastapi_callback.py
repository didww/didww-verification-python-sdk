"""A callback endpoint on FastAPI.

    DIDWW_SECRET=... uvicorn examples.fastapi_callback:app

The API calls your registered URL and waits for the answer before creating the
verification. There is one request and no retry: whatever you answer decides it.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request, Response

from didww_verification.callback import CallbackVerifier, allow, deny
from didww_verification.callback.fastapi import verify_request

app = FastAPI()

# The URL as REGISTERED with DIDWW, verbatim -- not the path the request arrives on.
# A registered URL with no path signs the empty string; a trailing slash differs.
verifier = CallbackVerifier(
    secret=os.environ["DIDWW_SECRET"],
    callback_url="https://example.com/callbacks/didww",
)


def is_expected(payload: dict[str, Any]) -> bool:
    """Your own rule: is this a verification you asked for?"""
    return payload.get("event") == "verification_request"


@app.post("/callbacks/didww")
async def didww_callback(request: Request) -> Response:
    if not await verify_request(verifier, request):
        # No reason in the body: it would be an oracle for which keys exist.
        return Response(status_code=401)

    payload = await request.json()
    body = allow() if is_expected(payload) else deny()
    return Response(body, media_type="application/json")
