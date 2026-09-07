"""The sync and async clients must be interchangeable.

They share every pure step -- building, signing, decoding -- and differ only in where
``send`` and ``sleep`` happen. These tests hold that line: if the two ever drift, one
of them is signing or encoding something the other does not, and only one set of
users finds out.
"""

from __future__ import annotations

import json
from typing import Any

import anyio
import httpx2
import pytest

from didww_verification import (
    ApplicationAuth,
    AsyncVerificationClient,
    CalloutOptions,
    SmsOptions,
    VerificationClient,
)
from didww_verification.config import RetryPolicy
from tests.conftest import FIXED_TIMESTAMP, SECRET, verification_payload

CALLS: list[tuple[str, dict[str, Any]]] = [
    (
        "start_verification",
        {
            "destination": "+371 123-456-78",
            "delivery_method": "sms",
            "sms": SmsOptions(languages=["lv-LV", "en-US"], app_hash="abcdefghijk"),
        },
    ),
    (
        "start_verification",
        {
            "destination": "+37112345678",
            "delivery_method": "callout",
            "callout": CalloutOptions(languages=["de-DE"]),
        },
    ),
    ("get_verification", {"verification_id": "a+b/c"}),
    ("report_verification", {"verification_id": "abc", "delivery_method": "sms", "code": "123456"}),
    ("get_verification_by_number", {"number": "+371.123 456-78"}),
    (
        "report_verification_by_number",
        {"number": "+37112345678", "delivery_method": "sms", "code": "123456"},
    ),
    (
        "report_verification_raw",
        {
            "verification_id": "abc",
            "delivery_method": "a_channel_this_release_does_not_model",
            "code": "123456",
        },
    ),
]


def _transport() -> tuple[httpx2.MockTransport, list[httpx2.Request]]:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, content=json.dumps({"data": verification_payload()}))

    return httpx2.MockTransport(handler), seen


def _policy() -> RetryPolicy:
    return RetryPolicy(attempts=2, base_delay=0.0, clock=lambda: FIXED_TIMESTAMP, rand=lambda: 0.0)


def _fingerprint(request: httpx2.Request) -> tuple[Any, ...]:
    headers = {k: v for k, v in request.headers.items() if k not in ("host", "user-agent")}
    return (request.method, request.url.raw_path, request.content, tuple(sorted(headers.items())))


_IDS = [f"{name}{i}" for i, (name, _) in enumerate(CALLS)]


@pytest.mark.parametrize(("method", "kwargs"), CALLS, ids=_IDS)
def test_both_clients_emit_byte_identical_requests(method: str, kwargs: dict[str, Any]) -> None:
    sync_transport, sync_seen = _transport()
    with VerificationClient(
        ApplicationAuth("k", SECRET),
        base_url="https://v.test",
        http_client=httpx2.Client(transport=sync_transport),
        retry=_policy(),
    ) as sync_client:
        getattr(sync_client, method)(**kwargs)

    async_transport, async_seen = _transport()

    async def run() -> None:
        async with AsyncVerificationClient(
            ApplicationAuth("k", SECRET),
            base_url="https://v.test",
            http_client=httpx2.AsyncClient(transport=async_transport),
            retry=_policy(),
        ) as async_client:
            await getattr(async_client, method)(**kwargs)

    anyio.run(run)

    assert _fingerprint(sync_seen[0]) == _fingerprint(async_seen[0])


def test_both_clients_decode_to_an_equal_verification() -> None:
    sync_transport, _ = _transport()
    with VerificationClient(
        ApplicationAuth("k", SECRET),
        base_url="https://v.test",
        http_client=httpx2.Client(transport=sync_transport),
        retry=_policy(),
    ) as sync_client:
        from_sync = sync_client.get_verification("abc")

    async_transport, _ = _transport()

    async def run() -> object:
        async with AsyncVerificationClient(
            ApplicationAuth("k", SECRET),
            base_url="https://v.test",
            http_client=httpx2.AsyncClient(transport=async_transport),
            retry=_policy(),
        ) as c:
            return await c.get_verification("abc")

    assert from_sync == anyio.run(run)
