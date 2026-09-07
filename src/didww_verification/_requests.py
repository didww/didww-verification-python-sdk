"""Request construction and signing. Pure: builds values, performs no I/O."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any, Literal, cast
from urllib.parse import quote

import httpx2

from .auth import Auth, BasicAuth, PublicAuth
from .models import CalloutOptions, SmsOptions
from .phone_number import digits_of
from .signing import sign, string_to_sign

__all__ = [
    "RequestSpec",
    "apply_auth",
    "build_get",
    "build_get_by_number",
    "build_report",
    "build_report_by_number",
    "build_start",
]

API_PREFIX = "/api/v1"
Method = Literal["GET", "POST", "PATCH", "DELETE"]


@dataclass(frozen=True, slots=True)
class RequestSpec:
    """A request, described but not sent."""

    method: Method
    path: str
    """Percent-encoded, query excluded."""
    body: bytes | None
    """``None`` means no body, which also means no ``Content-Type`` header."""
    query: Mapping[str, str] | None = None
    """Excluded from the signature, as the service excludes it."""


def _encode(data: Mapping[str, Any]) -> bytes:
    """Serialize the ``data`` envelope.

    Separators are pinned so the bytes are stable: they are what Content-MD5 covers.
    """
    return json.dumps({"data": data}, separators=(",", ":")).encode("utf-8")


def _channel_block(options: SmsOptions | CalloutOptions) -> dict[str, Any]:
    """Serialize a channel's options: every field that is set, under its own name.

    Reflective rather than hand-listed, so a field added to the dataclass reaches the
    wire without a second edit here. Hand-listing dropped such a field silently -- a
    valid request with the option missing and no error anywhere.

    ``list()`` matters: the annotation is ``Sequence``, and a tuple survives
    ``json.dumps`` while a range or a custom sequence does not.
    """
    block: dict[str, Any] = {}
    for field in fields(options):
        value: object = getattr(options, field.name)
        if value is None:
            continue
        if isinstance(value, Sequence) and not isinstance(value, str):
            value = list(cast("Sequence[object]", value))
        block[field.name] = value
    return block


def build_start(
    *,
    destination: str,
    delivery_method: str,
    sms: SmsOptions | None = None,
    callout: CalloutOptions | None = None,
) -> RequestSpec:
    """``POST /api/v1/verifications``.

    Per-channel options travel in a block named after the channel; the service reads
    only the block matching ``delivery_method``, so sending both is harmless. It drops
    an option it does not recognise but rejects a malformed value for one it does.
    """
    data: dict[str, Any] = {"destination": destination, "delivery_method": delivery_method}
    if sms is not None:
        data["sms"] = _channel_block(sms)
    if callout is not None:
        data["callout"] = _channel_block(callout)
    return RequestSpec("POST", f"{API_PREFIX}/verifications", _encode(data))


def build_get(verification_id: str) -> RequestSpec:
    """``GET /api/v1/verifications/{id}``."""
    return RequestSpec("GET", f"{API_PREFIX}/verifications/{quote(verification_id, safe='')}", None)


def build_report(verification_id: str, *, delivery_method: str, code: str) -> RequestSpec:
    """``PATCH /api/v1/verifications/{id}``.

    Reporting consumes one of a small number of attempts, so this is never retried
    automatically.
    """
    return RequestSpec(
        "PATCH",
        f"{API_PREFIX}/verifications/{quote(verification_id, safe='')}",
        _encode({"delivery_method": delivery_method, "code": code}),
    )


def build_get_by_number(number: str) -> RequestSpec:
    """``GET /api/v1/verifications/by_number/{number}``.

    Resolves to the newest verification for the number, finished ones included.
    """
    return RequestSpec("GET", f"{API_PREFIX}/verifications/by_number/{digits_of(number)}", None)


def build_report_by_number(number: str, *, delivery_method: str, code: str) -> RequestSpec:
    """``PATCH /api/v1/verifications/by_number/{number}``."""
    return RequestSpec(
        "PATCH",
        f"{API_PREFIX}/verifications/by_number/{digits_of(number)}",
        _encode({"delivery_method": delivery_method, "code": code}),
    )


def apply_auth(request: httpx2.Request, auth: Auth, timestamp: int) -> None:
    """Attach the scheme's headers to an already-built request, in place.

    Must run after the request is fully built: a signature covers the exact bytes and
    the exact path that go on the wire.

    * The signed path comes from ``raw_path`` with the query stripped. The decoded
      ``url.path`` turns ``%2B`` back into ``+`` and signs the wrong string.
    * A bodyless request sends *no* ``Content-Type``. The header is deleted rather
      than left unset, because a caller-supplied client can carry a default one.
    """
    if request.content:
        content_type = request.headers.get("content-type", "")
    else:
        request.headers.pop("content-type", None)
        content_type = ""

    if isinstance(auth, PublicAuth):
        request.headers["Authorization"] = f"Application {auth.key}"
        return

    if isinstance(auth, BasicAuth):
        token = base64.b64encode(f"{auth.key}:{auth.secret}".encode()).decode("ascii")
        request.headers["Authorization"] = f"Basic {token}"
        return

    # Narrowed to ApplicationAuth by the two returns above.
    path = request.url.raw_path.split(b"?", 1)[0].decode("ascii")
    signature = sign(
        auth.key_bytes(),
        string_to_sign(
            method=request.method,
            path=path,
            content_type=content_type,
            body=request.content or None,
            timestamp=timestamp,
        ),
    )
    request.headers["Authorization"] = f"Application {auth.key}:{signature}"
    request.headers["x-timestamp"] = str(timestamp)
