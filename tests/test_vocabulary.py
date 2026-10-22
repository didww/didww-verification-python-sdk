"""The vocabulary, and the invariant that keeps it sound."""

from __future__ import annotations

from typing import get_args

import pytest

from didww_verification import vocabulary as v


class TestTupleAndLiteralAgree:
    """Python cannot derive a Literal from a tuple the way TypeScript can, so the
    two are separate hand-maintained copies. If they drift, ``is_known_*`` returns
    True for a value outside its Literal and narrows it to a type it does not have --
    unsound, and nothing else in the toolchain notices.
    """

    @pytest.mark.parametrize(
        ("alias", "tup"),
        [
            (v.KnownDeliveryMethod, v.DELIVERY_METHODS),
            (v.KnownAutofillType, v.AUTOFILL_TYPES),
            (v.KnownVerificationStatus, v.VERIFICATION_STATUSES),
            (v.KnownTemplateFallbackReason, v.TEMPLATE_FALLBACK_REASONS),
            (v.KnownVerificationErrorCode, v.VERIFICATION_ERROR_CODES),
            (v.KnownApiErrorCode, v.API_ERROR_CODES),
        ],
        ids=[
            "delivery_method",
            "autofill_type",
            "status",
            "template_fallback_reason",
            "verification_error_code",
            "api_error_code",
        ],
    )
    def test_literal_members_equal_tuple_members(self, alias: object, tup: tuple[str, ...]) -> None:
        assert set(get_args(alias)) == set(tup)


class TestShape:
    def test_the_sdk_knows_39_slugs(self) -> None:
        """The service's 28 envelope and 11 outcome slugs (one is both), plus stale_dispatch."""
        assert len(v.API_ERROR_CODES) == 39
        assert len(v.VERIFICATION_ERROR_CODES) == 12

    def test_every_outcome_code_is_in_the_combined_set(self) -> None:
        """Not a subset of the *envelope* codes: an outcome arrives on a 200 and never
        in an errors envelope. ``API_ERROR_CODES`` is the union of the two sources."""
        assert set(v.VERIFICATION_ERROR_CODES) <= set(v.API_ERROR_CODES)

    def test_there_are_no_duplicates(self) -> None:
        assert len(set(v.API_ERROR_CODES)) == len(v.API_ERROR_CODES)

    def test_delivery_methods_and_statuses(self) -> None:
        assert v.DELIVERY_METHODS == ("sms", "callout")
        assert set(v.VERIFICATION_STATUSES) == {
            "pending",
            "verified",
            "failed",
            "expired",
            "denied",
        }


class TestPredicates:
    def test_known_values_are_recognised(self) -> None:
        assert v.is_known_delivery_method("sms")
        assert v.is_known_autofill_type("domain")
        assert v.is_known_verification_status("pending")
        assert v.is_known_api_error_code("unauthorized")
        assert v.is_known_verification_error_code("superseded")
        assert v.is_known_template_fallback_reason("language_missing")

    def test_the_deprecated_stale_dispatch_is_still_recognised(self) -> None:
        """The service no longer sends it, but code that matches on it keeps type-checking."""
        assert v.is_known_verification_error_code("stale_dispatch")

    def test_an_unmodelled_value_is_not_recognised_but_does_not_raise(self) -> None:
        """Decoding is fail-open: a value added after this release is just a string."""
        assert not v.is_known_delivery_method("some_new_channel")
        assert not v.is_known_autofill_type("some_new_type")
        assert not v.is_known_verification_status("some_new_status")
        assert not v.is_known_api_error_code("some_new_code")
        assert not v.is_known_template_fallback_reason("some_new_reason")


class TestTheVendoredContractAgrees:
    """The snapshot in contract/ and the exported vocabularies are two copies of the
    same facts. If they disagree, one of them was edited alone."""

    @staticmethod
    def _contract() -> dict[str, list[str]]:
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "contract" / "wire_contract.json"
        loaded: dict[str, list[str]] = json.loads(path.read_text())
        return loaded

    def test_delivery_methods_match(self) -> None:
        assert list(v.DELIVERY_METHODS) == self._contract()["deliveryMethods"]

    def test_statuses_match(self) -> None:
        assert list(v.VERIFICATION_STATUSES) == self._contract()["statuses"]

    def test_error_codes_match(self) -> None:
        contract = self._contract()
        envelope = contract["envelopeErrorCodes"]
        outcome = [c for c in contract["verificationErrorCodes"] if c not in envelope]
        assert list(v.API_ERROR_CODES) == envelope + outcome

    def test_template_fallback_reasons_match(self) -> None:
        assert list(v.TEMPLATE_FALLBACK_REASONS) == self._contract()["templateFallbackReasons"]

    def test_outcome_codes_match(self) -> None:
        assert list(v.VERIFICATION_ERROR_CODES) == self._contract()["verificationErrorCodes"]
