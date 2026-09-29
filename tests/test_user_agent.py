"""The User-Agent header is fixed, and the deprecated parameter cannot change it.

``user_agent`` shipped as a constructor parameter before the SDK settled on a single
identifying string; it is kept only so old callers do not break on upgrade.
"""

from __future__ import annotations

import anyio
import httpx2
import pytest

from didww_verification import ApplicationAuth, AsyncVerificationClient, VerificationClient
from didww_verification.config import DEFAULT_USER_AGENT
from tests.conftest import SECRET, recording_transport


def test_sync_client_sends_the_default_user_agent() -> None:
    transport, seen = recording_transport()
    VerificationClient(
        ApplicationAuth("k", SECRET),
        base_url="https://v.test",
        http_client=httpx2.Client(transport=transport),
    ).get_verification("abc")
    assert seen[0].headers["user-agent"] == DEFAULT_USER_AGENT


def test_async_client_sends_the_default_user_agent() -> None:
    transport, seen = recording_transport()

    async def run() -> None:
        async with AsyncVerificationClient(
            ApplicationAuth("k", SECRET),
            base_url="https://v.test",
            http_client=httpx2.AsyncClient(transport=transport),
        ) as client:
            await client.get_verification("abc")

    anyio.run(run)
    assert seen[0].headers["user-agent"] == DEFAULT_USER_AGENT


def test_sync_client_warns_and_still_sends_the_default_when_user_agent_is_passed() -> None:
    transport, seen = recording_transport()
    with pytest.deprecated_call():
        client = VerificationClient(
            ApplicationAuth("k", SECRET),
            base_url="https://v.test",
            http_client=httpx2.Client(transport=transport),
            user_agent="some/custom-agent",
        )
    client.get_verification("abc")
    assert seen[0].headers["user-agent"] == DEFAULT_USER_AGENT


def test_async_client_warns_and_still_sends_the_default_when_user_agent_is_passed() -> None:
    transport, seen = recording_transport()

    async def run() -> None:
        with pytest.deprecated_call():
            client = AsyncVerificationClient(
                ApplicationAuth("k", SECRET),
                base_url="https://v.test",
                http_client=httpx2.AsyncClient(transport=transport),
                user_agent="some/custom-agent",
            )
        async with client:
            await client.get_verification("abc")

    anyio.run(run)
    assert seen[0].headers["user-agent"] == DEFAULT_USER_AGENT


def test_a_supplied_http_client_with_its_own_default_is_overridden() -> None:
    """The negative control: a caller-supplied client's own default must not survive."""
    transport, seen = recording_transport()
    http = httpx2.Client(transport=transport, headers={"user-agent": "caller/1.0"})
    VerificationClient(
        ApplicationAuth("k", SECRET),
        base_url="https://v.test",
        http_client=http,
    ).get_verification("abc")
    assert seen[0].headers["user-agent"] == DEFAULT_USER_AGENT
