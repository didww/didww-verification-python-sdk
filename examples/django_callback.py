"""A callback endpoint on Django.

Wire it into your URLconf:

    path("callbacks/didww", didww_callback)
"""

from __future__ import annotations

import json
import os

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from didww_verification.callback import CallbackVerifier, allow, deny
from didww_verification.callback.django import verify_request

verifier = CallbackVerifier(
    secret=os.environ["DIDWW_SECRET"],
    callback_url="https://example.com/callbacks/didww",
)


# CSRF-exempt: the request comes from DIDWW, not a form, and carries its own signature.
@csrf_exempt
def didww_callback(request: HttpRequest) -> HttpResponse:
    # Verify before touching request.POST: that consumes the stream.
    if not verify_request(verifier, request):
        return HttpResponse(status=401)

    payload = json.loads(request.body)
    body = allow() if payload.get("event") == "verification_request" else deny()
    return HttpResponse(body, content_type="application/json")
