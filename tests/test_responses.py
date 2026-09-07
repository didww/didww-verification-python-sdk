"""Decoding, including every nullability the wire actually produces."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from didww_verification import (
    DidwwApiError,
    DidwwBalanceInsufficientError,
    DidwwDecodingError,
    DidwwNotFoundError,
    DidwwServerError,
    DidwwTransportError,
    DidwwUnauthorizedError,
    DidwwValidationError,
)
from didww_verification._responses import HttpOutcome, TransportFailure, decode_verification
from tests.conftest import verification_payload


def ok(**overrides: object) -> HttpOutcome:
    return HttpOutcome(200, json.dumps({"data": verification_payload(**overrides)}).encode())


class TestSuccess:
    def test_decodes_a_pending_sms_verification(self) -> None:
        v = decode_verification(ok())
        assert v.status == "pending"
        assert v.delivery_method == "sms"
        assert v.fee == Decimal("0.0450")
        assert v.sms is not None and v.sms.language == "en-US"
        assert v.callout is None
        assert not v.is_finished

    def test_fee_is_a_decimal_not_a_float(self) -> None:
        """The wire sends a decimal string; money must not round."""
        assert decode_verification(ok(fee="0.1")).fee == Decimal("0.1")

    def test_expires_at_carries_a_trailing_z(self) -> None:
        """datetime.fromisoformat cannot read this before 3.11, which is the floor."""
        v = decode_verification(ok())
        assert v.expires_at is not None
        assert v.expires_at.utcoffset() is not None
        assert v.expires_at.isoformat() == "2026-09-03T12:00:00+00:00"

    @pytest.mark.parametrize("field", ["fee", "expires_at", "error_code", "error_detail"])
    def test_nullable_fields_may_be_null(self, field: str) -> None:
        assert getattr(decode_verification(ok(**{field: None})), field) is None

    def test_an_unmodelled_status_or_channel_decodes_rather_than_raising(self) -> None:
        v = decode_verification(ok(status="some_new_status", delivery_method="some_new_channel"))
        assert v.status == "some_new_status"
        assert v.delivery_method == "some_new_channel"
        assert v.is_finished  # anything not pending is terminal

    def test_a_finished_verification_is_data_not_an_exception(self) -> None:
        v = decode_verification(ok(status="failed", error_code="too_many_attempts"))
        assert (v.status, v.error_code) == ("failed", "too_many_attempts")
        assert v.is_finished

    def test_raw_is_withheld_by_default_and_kept_on_request(self) -> None:
        assert decode_verification(ok()).raw is None
        assert decode_verification(ok(), keep_raw_payload=True) is not None

    def test_a_verification_is_hashable(self) -> None:
        """frozen=True advertises hashability; a mapping field would break it."""
        v = decode_verification(ok(), keep_raw_payload=True)
        assert hash(v) == hash(decode_verification(ok(), keep_raw_payload=True))
        assert len({v, decode_verification(ok())}) == 1

    def test_the_sms_block_is_absent_for_a_callout(self) -> None:
        payload = verification_payload(delivery_method="callout", callout={"language": "de-DE"})
        del payload["sms"]
        v = decode_verification(HttpOutcome(200, json.dumps({"data": payload}).encode()))
        assert v.sms is None
        assert v.callout is not None and v.callout.language == "de-DE"


class TestErrors:
    @pytest.mark.parametrize(
        ("status", "cls"),
        [
            (400, DidwwValidationError),
            (401, DidwwUnauthorizedError),
            (402, DidwwBalanceInsufficientError),
            (404, DidwwNotFoundError),
            (422, DidwwValidationError),
            (500, DidwwServerError),
            (503, DidwwServerError),
            (418, DidwwApiError),
        ],
    )
    def test_status_maps_to_an_exception_class(self, status: int, cls: type) -> None:
        body = b'{"errors":[{"code":"unauthorized","detail":"unauthorized"}]}'
        with pytest.raises(cls):
            decode_verification(HttpOutcome(status, body))

    def test_every_error_in_the_envelope_is_kept(self) -> None:
        """A validation failure returns one entry per field, so errors[0] is not enough."""
        body = json.dumps(
            {
                "errors": [
                    {"code": "destination_blank", "detail": "destination can't be blank"},
                    {"code": "code_blank", "detail": "code can't be blank"},
                ]
            }
        ).encode()
        with pytest.raises(DidwwValidationError) as excinfo:
            decode_verification(HttpOutcome(422, body))
        assert excinfo.value.codes == ("destination_blank", "code_blank")
        assert excinfo.value.has_code("code_blank")

    def test_a_non_json_error_body_is_still_the_status_error(self) -> None:
        """A 502 from an ingress is a server error, not a bug in this SDK."""
        with pytest.raises(DidwwServerError) as excinfo:
            decode_verification(HttpOutcome(502, b"<html>Bad Gateway</html>"))
        assert excinfo.value.errors == ()
        assert excinfo.value.status == 502

    def test_a_transport_failure_becomes_a_transport_error(self) -> None:
        with pytest.raises(DidwwTransportError):
            decode_verification(TransportFailure(OSError("connection reset")))

    @pytest.mark.parametrize(
        "body",
        [b"not json", b"[]", b'{"nope":1}', b'{"data":[]}'],
        ids=["not-json", "array", "no-data", "data-not-object"],
    )
    def test_an_unreadable_2xx_body_is_a_decoding_error(self, body: bytes) -> None:
        with pytest.raises(DidwwDecodingError):
            decode_verification(HttpOutcome(200, body))

    def test_a_malformed_timestamp_is_a_decoding_error(self) -> None:
        with pytest.raises(DidwwDecodingError):
            decode_verification(ok(expires_at="2026-02-30T00:00:00Z"))

    def test_the_retained_body_is_truncated(self) -> None:
        """It can carry the destination, and exceptions end up in logs."""
        with pytest.raises(DidwwServerError) as excinfo:
            decode_verification(HttpOutcome(500, b"x" * 5000))
        assert excinfo.value.body is not None
        assert len(excinfo.value.body) == 512
