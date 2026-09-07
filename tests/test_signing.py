"""Signer tests.

The vectors come from the service, not from this signer. That matters: checking this
SDK's signer against itself proves only self-consistency, which is exactly what a
signing bug preserves.
"""

from __future__ import annotations

import pytest

from didww_verification.errors import DidwwConfigurationError
from didww_verification.secret import decode_secret
from didww_verification.signing import sign, string_to_sign

SECRET = "tEsT_secret_urlsafe_base64_value_AA"


def _sign(**kw: object) -> str:
    return sign(decode_secret(SECRET), string_to_sign(**kw))  # type: ignore[arg-type]


def test_matches_the_service_vector_for_a_signed_post() -> None:
    assert (
        _sign(
            method="POST",
            path="/verifications",
            content_type="application/json",
            body=b'{"key":"value"}',
            timestamp=1700000000,
        )
        == "k7TRVTzybQtVKYdpgKNd2QxH5n2LvQselVWSMOlYPo8="
    )


def test_matches_the_service_vector_for_a_bodyless_get() -> None:
    assert (
        _sign(
            method="GET",
            path="/verifications",
            content_type="",
            body=None,
            timestamp=1700000000,
        )
        == "kCJ2eLWCrmKMhEsBFRL1A8HcmBTozeljcfOy5i+kVZU="
    )


def test_string_to_sign_is_five_lines_with_no_trailing_newline() -> None:
    sts = string_to_sign(
        method="POST",
        path="/verifications",
        content_type="application/json",
        body=b'{"key":"value"}',
        timestamp=1700000000,
    )
    assert sts.decode().split("\n") == [
        "POST",
        "pzU/fN3OgI3gAydHoLe+UA==",  # openssl md5 of the body, cross-checked
        "application/json",
        "x-timestamp:1700000000",
        "/verifications",
    ]


def test_method_is_upcased() -> None:
    kw = {"path": "/x", "content_type": "", "body": None, "timestamp": 1}
    assert _sign(method="get", **kw) == _sign(method="GET", **kw)


def test_body_is_signed_byte_exactly() -> None:
    kw = {"method": "POST", "path": "/x", "content_type": "application/json", "timestamp": 1}
    assert _sign(body=b'{"a":1}', **kw) != _sign(body=b'{"a":1} ', **kw)


@pytest.mark.parametrize("body", [None, b"", b"   ", b"\n\t "])
def test_a_blank_or_whitespace_only_body_signs_an_empty_content_md5(body: bytes | None) -> None:
    """The service tests the body for presence, not emptiness.

    A whitespace-only body therefore signs as "" server-side. Hashing it instead
    disagrees with the service on every such request, and the only symptom is a 401.
    """
    sts = string_to_sign(
        method="POST", path="/x", content_type="application/json", body=body, timestamp=1
    )
    assert sts.decode().split("\n")[1] == ""


class TestDecodeSecret:
    def test_accepts_an_unpadded_secret(self) -> None:
        """Issued secrets are not always a multiple of four characters."""
        assert decode_secret(SECRET) == decode_secret(SECRET + "=")

    @pytest.mark.parametrize("tail", ["AA", "AB", "AC", "AD"])
    def test_accepts_a_non_canonical_final_quantum(self, tail: str) -> None:
        """The bits outside the last whole byte carry no key material.

        Rejecting these would refuse a secret that authenticates correctly against
        the service and every other SDK.
        """
        assert decode_secret(f"tEsT_secret_urlsafe_base64_value_{tail}") == decode_secret(SECRET)

    def test_accepts_both_base64_alphabets(self) -> None:
        assert decode_secret("ab-c_def") == decode_secret("ab+c/def")

    @pytest.mark.parametrize(
        "bad",
        [
            "tEsT_secret urlsafe_base64_value_AA",
            "tEsT_secret\nurlsafe_base64_value_AA",
            "tEsT\u2013secret_urlsafe_base64_value_AA",  # en-dash, as a word processor pastes it
            "abcde",
            "",
            "====",
        ],
        ids=["space", "newline", "en-dash", "bad-length", "empty", "padding-only"],
    )
    def test_rejects_what_cannot_be_a_secret(self, bad: str) -> None:
        with pytest.raises(DidwwConfigurationError):
            decode_secret(bad)
