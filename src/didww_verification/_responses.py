"""Response decoding. Pure: given an outcome, returns a Verification or raises."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TypeAlias, cast

from ._datetime import parse_timestamp
from .errors import (
    DidwwApiError,
    DidwwBalanceInsufficientError,
    DidwwDecodingError,
    DidwwNotFoundError,
    DidwwServerError,
    DidwwTransportError,
    DidwwUnauthorizedError,
    DidwwValidationError,
    ErrorItem,
)
from .models import CalloutInfo, SmsInfo, Verification

__all__ = [
    "HttpOutcome",
    "Outcome",
    "TransportFailure",
    "data_list_of",
    "data_of",
    "decode_verification",
    "envelope_of",
    "no_content",
]

_BODY_LIMIT = 512


@dataclass(frozen=True, slots=True)
class HttpOutcome:
    """A response arrived, whatever its status."""

    status: int
    body: bytes


@dataclass(frozen=True, slots=True)
class TransportFailure:
    """No response arrived: connect, timeout, TLS, pool."""

    cause: Exception


Outcome: TypeAlias = HttpOutcome | TransportFailure


def _snippet(body: bytes) -> str:
    """A short, safe excerpt of a body for diagnostics.

    Truncated because the body can carry the destination number, and an exception
    tends to end up in a log.
    """
    return body[:_BODY_LIMIT].decode("utf-8", errors="replace")


def _error_class(status: int) -> type[DidwwApiError]:
    if status == 401:
        return DidwwUnauthorizedError
    if status == 402:
        return DidwwBalanceInsufficientError
    if status == 404:
        return DidwwNotFoundError
    if status in (400, 422):
        return DidwwValidationError
    if 500 <= status <= 599:
        return DidwwServerError
    return DidwwApiError


def _parse_errors(body: bytes) -> tuple[ErrorItem, ...]:
    """Read the ``{"errors": [...]}`` envelope, tolerating anything that is not one.

    A proxy or an unrouted path can answer with HTML or nothing. That is a server
    error, not a decoding bug, so an unreadable body yields no items rather than
    raising.
    """
    try:
        parsed: object = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return ()
    if not isinstance(parsed, dict):
        return ()
    raw: object = cast("dict[str, object]", parsed).get("errors")
    if not isinstance(raw, list):
        return ()
    items: list[ErrorItem] = []
    for entry in cast("list[object]", raw):
        if isinstance(entry, dict):
            fields = cast("dict[str, object]", entry)
            code = fields.get("code")
            detail = fields.get("detail")
            items.append(
                ErrorItem(
                    code if isinstance(code, str) else None,
                    detail if isinstance(detail, str) else None,
                )
            )
        else:
            items.append(ErrorItem(None, str(entry)))
    return tuple(items)


def _optional_str(value: object, field: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise DidwwDecodingError(f"{field} is not a string: {value!r}")


def _required_str(value: object, field: str) -> str:
    if isinstance(value, str):
        return value
    raise DidwwDecodingError(f"{field} is missing or not a string: {value!r}")


def _sms(block: object) -> SmsInfo | None:
    if block is None:
        return None
    if not isinstance(block, dict):
        raise DidwwDecodingError(f"sms is not an object: {block!r}")
    fields = cast("dict[str, object]", block)
    timeout = fields.get("interception_timeout")
    if timeout is not None and not isinstance(timeout, int):
        raise DidwwDecodingError(f"sms.interception_timeout is not an integer: {timeout!r}")
    return SmsInfo(
        template=_optional_str(fields.get("template"), "sms.template"),
        language=_optional_str(fields.get("language"), "sms.language"),
        interception_timeout=timeout,
        app_hash=_optional_str(fields.get("app_hash"), "sms.app_hash"),
    )


def _callout(block: object) -> CalloutInfo | None:
    if block is None:
        return None
    if not isinstance(block, dict):
        raise DidwwDecodingError(f"callout is not an object: {block!r}")
    fields = cast("dict[str, object]", block)
    return CalloutInfo(language=_optional_str(fields.get("language"), "callout.language"))


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DidwwDecodingError(f"{field} is not a decimal: {value!r}") from exc


def _optional_timestamp(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        return parse_timestamp(_required_str(value, field))
    except ValueError as exc:
        raise DidwwDecodingError(f"{field} is not a timestamp: {exc}") from exc


def _checked_body(outcome: Outcome) -> bytes:
    """The body of a successful response. Raises for a transport fault or a non-2xx."""
    if isinstance(outcome, TransportFailure):
        raise DidwwTransportError(str(outcome.cause)) from outcome.cause

    if not 200 <= outcome.status < 300:
        raise _error_class(outcome.status)(
            status=outcome.status, errors=_parse_errors(outcome.body), body=_snippet(outcome.body)
        )
    return outcome.body


def no_content(outcome: Outcome) -> None:
    """For an endpoint that answers 204, or 200 with nothing worth reading.

    Still raises on a transport fault and a non-2xx, so a delete reports failure the
    same way every other call does.
    """
    _checked_body(outcome)


def envelope_of(outcome: Outcome) -> dict[str, object]:
    """The whole envelope of a successful response, or raise.

    Everything entity-independent happens here: a transport fault, a non-2xx, a body
    that is not JSON, a payload that is not an object. What ``data`` holds is left to
    the caller, so a decoder that needs a sibling key such as ``meta`` can read it.
    """
    body = _checked_body(outcome)
    try:
        payload: object = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DidwwDecodingError(f"response body is not JSON: {exc}", body=_snippet(body)) from exc

    if not isinstance(payload, dict):
        raise DidwwDecodingError("response is not an object", body=_snippet(body))
    return cast("dict[str, object]", payload)


def data_of(outcome: Outcome) -> dict[str, object]:
    """The ``data`` object of a single-resource response.

    A decoder for a new entity starts here and only reads fields.
    """
    data = envelope_of(outcome).get("data")
    if not isinstance(data, dict):
        raise DidwwDecodingError(f"response has no 'data' object, got {type(data).__name__}")
    return cast("dict[str, object]", data)


def data_list_of(outcome: Outcome) -> list[dict[str, object]]:
    """The ``data`` array of a collection response, entry by entry.

    Pagination is deliberately not modelled: no endpoint here returns a collection
    yet, so its envelope is undecided. Read ``meta`` from :func:`envelope_of` when one
    exists rather than guessing a shape now.
    """
    data = envelope_of(outcome).get("data")
    if not isinstance(data, list):
        raise DidwwDecodingError(f"response has no 'data' array, got {type(data).__name__}")
    entries = cast("list[object]", data)
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DidwwDecodingError(f"data[{index}] is not an object: {entry!r}")
    return cast("list[dict[str, object]]", entries)


def decode_verification(outcome: Outcome, *, keep_raw_payload: bool = False) -> Verification:
    """Turn an outcome into a Verification, or raise.

    A verification that ended ``failed``, ``expired`` or ``denied`` is a *success*
    here. Only a non-2xx, a transport fault, or an unreadable 2xx body raises.
    """
    data = data_of(outcome)
    return Verification(
        id=_required_str(data.get("id"), "id"),
        destination=_required_str(data.get("destination"), "destination"),
        delivery_method=_required_str(data.get("delivery_method"), "delivery_method"),
        fee=_optional_decimal(data.get("fee"), "fee"),
        status=_required_str(data.get("status"), "status"),
        error_code=_optional_str(data.get("error_code"), "error_code"),
        error_detail=_optional_str(data.get("error_detail"), "error_detail"),
        expires_at=_optional_timestamp(data.get("expires_at"), "expires_at"),
        sms=_sms(data.get("sms")),
        callout=_callout(data.get("callout")),
        raw=data if keep_raw_payload else None,
    )
