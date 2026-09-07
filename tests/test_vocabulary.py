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
            (v.KnownVerificationStatus, v.VERIFICATION_STATUSES),
            (v.KnownVerificationErrorCode, v.VERIFICATION_ERROR_CODES),
            (v.KnownApiErrorCode, v.API_ERROR_CODES),
        ],
        ids=["delivery_method", "status", "verification_error_code", "api_error_code"],
    )
    def test_literal_members_equal_tuple_members(self, alias: object, tup: tuple[str, ...]) -> None:
        assert set(get_args(alias)) == set(tup)


class TestShape:
    def test_the_registry_has_27_slugs(self) -> None:
        """18 envelope plus 9 outcome, as the service defines them."""
        assert len(v.API_ERROR_CODES) == 27
        assert len(v.VERIFICATION_ERROR_CODES) == 9

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
        assert v.is_known_verification_status("pending")
        assert v.is_known_api_error_code("unauthorized")
        assert v.is_known_verification_error_code("superseded")

    def test_an_unmodelled_value_is_not_recognised_but_does_not_raise(self) -> None:
        """Decoding is fail-open: a value added after this release is just a string."""
        assert not v.is_known_delivery_method("some_new_channel")
        assert not v.is_known_verification_status("some_new_status")
        assert not v.is_known_api_error_code("some_new_code")


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
        expected = contract["envelopeErrorCodes"] + contract["verificationErrorCodes"]
        assert list(v.API_ERROR_CODES) == expected

    def test_outcome_codes_match(self) -> None:
        assert list(v.VERIFICATION_ERROR_CODES) == self._contract()["verificationErrorCodes"]
