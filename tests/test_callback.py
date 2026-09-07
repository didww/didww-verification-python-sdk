"""Inbound callback verification."""

from __future__ import annotations

import json

import pytest

from didww_verification.callback import (
    CallbackVerifier,
    RejectionReason,
    allow,
    deny,
    parse_authorization,
)
from didww_verification.errors import DidwwConfigurationError
from didww_verification.secret import decode_secret
from didww_verification.signing import sign, string_to_sign
from tests.conftest import SECRET

NOW = 1700000000
BODY = json.dumps(
    {
        "event": "verification_request",
        "data": {"id": "abc", "destination": "37112345678", "delivery_method": "sms"},
    }
).encode()


def signature_for(path: str, *, timestamp: int = NOW, body: bytes = BODY) -> str:
    return sign(
        decode_secret(SECRET),
        string_to_sign(
            method="POST",
            path=path,
            content_type="application/json",
            body=body,
            timestamp=timestamp,
        ),
    )


def verifier_for(url: str, tolerance: int = 300) -> CallbackVerifier:
    return CallbackVerifier(secret=SECRET, callback_url=url, tolerance=tolerance, clock=lambda: NOW)


def check(v: CallbackVerifier, signature: str | None, *, timestamp: object = NOW) -> object:
    return v.check(
        method="POST",
        content_type="application/json",
        body=BODY,
        timestamp=None if timestamp is None else str(timestamp),
        signature=signature,
    )


class TestSignedPathComesFromTheRegisteredUrl:
    """The service signs the registered URL's path, never the path the request
    arrives on. They differ whenever an ingress rewrites or the app is mounted under
    a prefix."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://example.com", ""),
            ("https://example.com?x=1", ""),
            ("https://example.com/", "/"),
            ("https://example.com/cb/didww", "/cb/didww"),
            ("https://example.com/cb?x=1", "/cb"),
        ],
    )
    def test_the_path_matches_the_services_own_derivation(self, url: str, expected: str) -> None:
        assert verifier_for(url).signed_path == expected

    def test_a_pathless_url_signs_the_empty_string_not_a_slash(self) -> None:
        """The trap. Defaulting to the received pathname signs "/" instead, which is
        a valid signature over the wrong string, and denies 100% of that
        application's verifications with correct code on both sides."""
        v = verifier_for("https://example.com")
        assert check(v, signature_for("")) is None
        assert check(v, signature_for("/")) is RejectionReason.BAD_SIGNATURE

    def test_a_trailing_slash_is_a_different_signature(self) -> None:
        assert check(verifier_for("https://example.com/"), signature_for("/")) is None
        v = verifier_for("https://example.com/")
        assert check(v, signature_for("")) is RejectionReason.BAD_SIGNATURE


class TestRejection:
    def test_a_valid_request_passes(self) -> None:
        v = verifier_for("https://example.com/cb")
        assert v.is_valid(
            method="POST",
            content_type="application/json",
            body=BODY,
            timestamp=str(NOW),
            signature=signature_for("/cb"),
        )

    def test_missing_signature(self) -> None:
        v = verifier_for("https://example.com/cb")
        assert check(v, None) is RejectionReason.MISSING_SIGNATURE

    def test_missing_timestamp(self) -> None:
        v = verifier_for("https://example.com/cb")
        got = check(v, signature_for("/cb"), timestamp=None)
        assert got is RejectionReason.MISSING_TIMESTAMP

    def test_malformed_timestamp(self) -> None:
        v = verifier_for("https://example.com/cb")
        got = check(v, signature_for("/cb"), timestamp="soon")
        assert got is RejectionReason.MALFORMED_TIMESTAMP

    @pytest.mark.parametrize("skew", [301, -301])
    def test_a_timestamp_outside_the_window_is_stale(self, skew: int) -> None:
        v = verifier_for("https://example.com/cb")
        stale = NOW + skew
        got = check(v, signature_for("/cb", timestamp=stale), timestamp=stale)
        assert got is RejectionReason.STALE_TIMESTAMP

    @pytest.mark.parametrize("skew", [299, -299, 0])
    def test_a_timestamp_inside_the_window_passes(self, skew: int) -> None:
        v = verifier_for("https://example.com/cb")
        t = NOW + skew
        assert check(v, signature_for("/cb", timestamp=t), timestamp=t) is None

    def test_a_tampered_body_fails(self) -> None:
        v = verifier_for("https://example.com/cb")
        assert (
            v.check(
                method="POST",
                content_type="application/json",
                body=BODY + b" ",
                timestamp=str(NOW),
                signature=signature_for("/cb"),
            )
            is RejectionReason.BAD_SIGNATURE
        )

    def test_a_negative_tolerance_is_rejected(self) -> None:
        with pytest.raises(DidwwConfigurationError):
            verifier_for("https://example.com/cb", tolerance=-1)

    def test_a_relative_callback_url_is_rejected(self) -> None:
        with pytest.raises(DidwwConfigurationError):
            CallbackVerifier(secret=SECRET, callback_url="/cb")


class TestParseAuthorization:
    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("Application key:sig", ("key", "sig")),
            ("Application key", (None, None)),
            ("Basic abc", (None, None)),
            ("", (None, None)),
            (None, (None, None)),
        ],
    )
    def test_parses_only_the_signed_form(
        self, header: str | None, expected: tuple[str | None, str | None]
    ) -> None:
        assert parse_authorization(header) == expected


def test_response_bodies_carry_no_diagnostic_detail() -> None:
    """Echoing why a request failed turns the endpoint into an oracle for which
    application keys exist."""
    assert json.loads(allow()) == {"action": "allow"}
    assert json.loads(deny()) == {"action": "deny"}
