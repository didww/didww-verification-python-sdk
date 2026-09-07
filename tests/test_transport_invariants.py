"""What actually goes on the wire.

These assert on the built request rather than on a round-trip through this SDK's own
signer. A signing bug is self-consistent by nature: the client and the signer agree
with each other and disagree only with the service, so a test that compares them
passes while every real request fails.
"""

from __future__ import annotations

import base64

import httpx2
import pytest

from didww_verification import (
    ApplicationAuth,
    BasicAuth,
    DidwwApiError,
    DidwwServerError,
    PublicAuth,
    VerificationClient,
)
from didww_verification.config import RetryPolicy
from tests.conftest import FIXED_TIMESTAMP, SECRET, recording_transport


def client_with(transport: httpx2.MockTransport, auth: object, **kw: object) -> VerificationClient:
    return VerificationClient(
        auth,  # type: ignore[arg-type]
        base_url="https://v.test",
        http_client=httpx2.Client(transport=transport),
        retry=RetryPolicy(
            attempts=2, base_delay=0.0, clock=lambda: FIXED_TIMESTAMP, rand=lambda: 0.0
        ),
        **kw,  # type: ignore[arg-type]
    )


class TestBodylessRequestsCarryNoContentType:
    def test_a_signed_get_sends_no_content_type(self) -> None:
        transport, seen = recording_transport()
        client_with(transport, ApplicationAuth("k", SECRET)).get_verification("abc")
        assert "content-type" not in seen[0].headers

    def test_even_when_the_supplied_client_sets_one_by_default(self) -> None:
        """The negative control, and the reason the header is deleted not merely unset.

        A caller may hand us a client with a default Content-Type. It is inherited by
        a bodyless request, lands in the signed string, and 401s every read against
        the real service while every self-consistent test still passes.
        """
        transport, seen = recording_transport()
        http = httpx2.Client(transport=transport, headers={"Content-Type": "application/json"})
        VerificationClient(
            ApplicationAuth("k", SECRET),
            base_url="https://v.test",
            http_client=http,
            retry=RetryPolicy(clock=lambda: FIXED_TIMESTAMP),
        ).get_verification("abc")
        assert "content-type" not in seen[0].headers


class TestSignedPath:
    def test_the_signed_path_is_the_undecoded_request_target(self) -> None:
        """url.path is decoded and would sign the wrong bytes; raw_path is not."""
        transport, seen = recording_transport()
        client_with(transport, ApplicationAuth("k", SECRET)).get_verification("a+b")
        request = seen[0]
        assert request.url.raw_path == b"/api/v1/verifications/a%2Bb"
        assert request.url.path == "/api/v1/verifications/a+b"

    def test_by_number_paths_carry_digits_only(self) -> None:
        """A '.' left in the last segment is read as a format suffix and truncates the lookup."""
        transport, seen = recording_transport()
        client_with(transport, BasicAuth("k", "s")).get_verification_by_number("+371.123 456-78")
        assert seen[0].url.raw_path == b"/api/v1/verifications/by_number/37112345678"


class TestAuthSchemes:
    def test_public_sends_the_key_alone(self) -> None:
        transport, seen = recording_transport()
        client_with(transport, PublicAuth("app-key")).get_verification("abc")
        assert seen[0].headers["authorization"] == "Application app-key"
        assert "x-timestamp" not in seen[0].headers

    def test_basic_sends_base64_key_colon_secret(self) -> None:
        transport, seen = recording_transport()
        client_with(transport, BasicAuth("k", "s")).get_verification("abc")
        expected = base64.b64encode(b"k:s").decode()
        assert seen[0].headers["authorization"] == f"Basic {expected}"

    def test_application_sends_a_signature_and_a_matching_timestamp(self) -> None:
        transport, seen = recording_transport()
        client_with(transport, ApplicationAuth("k", SECRET)).get_verification("abc")
        request = seen[0]
        assert request.headers["x-timestamp"] == str(FIXED_TIMESTAMP)
        scheme, credentials = request.headers["authorization"].split(" ", 1)
        key, signature = credentials.split(":", 1)
        assert (scheme, key) == ("Application", "k")
        assert signature


class TestRetry:
    def test_a_read_is_retried_and_re_signed_with_a_fresh_timestamp(self) -> None:
        """A signature reused across a slow retry can fall outside the replay window."""
        stamps = iter([1700000000, 1700000009])
        seen: list[httpx2.Request] = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            seen.append(request)
            return httpx2.Response(503, content=b"upstream unavailable")

        client = VerificationClient(
            ApplicationAuth("k", SECRET),
            base_url="https://v.test",
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            retry=RetryPolicy(
                attempts=2, base_delay=0.0, clock=lambda: next(stamps), rand=lambda: 0.0
            ),
        )
        with pytest.raises(DidwwServerError):
            client.get_verification("abc")

        assert [r.headers["x-timestamp"] for r in seen] == ["1700000000", "1700000009"]
        assert seen[0].headers["authorization"] != seen[1].headers["authorization"]

    @pytest.mark.parametrize("status", [400, 401, 402, 404, 422])
    def test_a_4xx_is_never_retried(self, status: int) -> None:
        transport, seen = recording_transport(
            status=status, body=b'{"errors":[{"code":"not_found"}]}'
        )
        with pytest.raises(DidwwApiError):
            client_with(transport, BasicAuth("k", "s")).get_verification("abc")
        assert len(seen) == 1

    def test_a_write_is_never_retried(self) -> None:
        """A repeated start supersedes and charges again; a repeated report burns an attempt."""
        transport, seen = recording_transport(status=503, body=b"nope")
        with pytest.raises(DidwwServerError):
            client_with(transport, BasicAuth("k", "s")).start_verification(
                destination="+37112345678", delivery_method="sms"
            )
        assert len(seen) == 1
