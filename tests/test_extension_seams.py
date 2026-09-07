"""The seams a new endpoint or entity has to fit through.

Each test here fails if adding one would require changing the driver, the signer or
the error mapping rather than adding a builder and a decoder beside the existing ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from typing import Any, cast

import httpx2
import pytest

from didww_verification import (
    ApplicationAuth,
    DidwwDecodingError,
    DidwwNotFoundError,
    DidwwServerError,
    VerificationClient,
)
from didww_verification._requests import API_PREFIX, RequestSpec, apply_auth, build_start
from didww_verification._responses import (
    Outcome,
    data_list_of,
    data_of,
    envelope_of,
    no_content,
)
from didww_verification.config import RetryPolicy
from didww_verification.models import CalloutOptions, SmsOptions
from didww_verification.secret import decode_secret
from didww_verification.signing import sign, string_to_sign
from tests.conftest import FIXED_TIMESTAMP, SECRET, recording_transport


def client_with(transport: httpx2.MockTransport, **kw: object) -> VerificationClient:
    return VerificationClient(
        ApplicationAuth("k", SECRET),
        base_url="https://v.test",
        http_client=httpx2.Client(transport=transport),
        retry=RetryPolicy(
            attempts=2, base_delay=0.0, clock=lambda: FIXED_TIMESTAMP, rand=lambda: 0.0
        ),
        **kw,  # type: ignore[arg-type]
    )


class TestAQueryStringDoesNotDisturbTheSignature:
    """Paged endpoints need query parameters. The service signs the path only, so
    adding them must leave the signature identical -- otherwise every list endpoint
    would need its own signing path."""

    @staticmethod
    def _signature_for(query: dict[str, str] | None) -> str:
        request = httpx2.Client(base_url="https://v.test").build_request(
            "GET", f"{API_PREFIX}/verifications", params=query
        )
        apply_auth(request, ApplicationAuth("k", SECRET), FIXED_TIMESTAMP)
        return request.headers["Authorization"]

    def test_query_parameters_leave_the_signature_unchanged(self) -> None:
        assert self._signature_for({"page": "2", "per_page": "50"}) == self._signature_for(None)

    def test_the_signature_is_the_one_the_service_computes(self) -> None:
        expected = sign(
            decode_secret(SECRET),
            string_to_sign(
                method="GET",
                path=f"{API_PREFIX}/verifications",
                content_type="",
                body=None,
                timestamp=FIXED_TIMESTAMP,
            ),
        )
        assert self._signature_for({"page": "2"}) == f"Application k:{expected}"

    def test_a_spec_query_reaches_the_wire(self) -> None:
        transport, seen = recording_transport()
        client = client_with(transport)
        client._execute(
            RequestSpec("GET", f"{API_PREFIX}/verifications", None, {"page": "2"}),
            lambda outcome: data_of(outcome),
        )
        assert seen[0].url.params["page"] == "2"


class TestANewEntityNeedsOnlyADecoder:
    """`_execute` is generic over the decoder, so a second entity reuses the retry,
    signing and error-mapping path untouched."""

    @dataclass(frozen=True, slots=True)
    class Application:
        id: str
        name: str

    @classmethod
    def _decode_application(cls, outcome: Outcome) -> Application:
        data = data_of(outcome)
        return cls.Application(id=str(data["id"]), name=str(data["name"]))

    def test_a_foreign_decoder_runs_through_the_same_driver(self) -> None:
        def handler(_request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, json={"data": {"id": "app-1", "name": "Checkout"}})

        client = client_with(httpx2.MockTransport(handler))
        result = client._execute(
            RequestSpec("GET", f"{API_PREFIX}/applications/app-1", None),
            self._decode_application,
        )
        assert result == self.Application(id="app-1", name="Checkout")

    def test_it_inherits_the_error_mapping(self) -> None:
        def handler(_request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(
                404, content=json.dumps({"errors": [{"code": "not_found", "detail": "No such"}]})
            )

        client = client_with(httpx2.MockTransport(handler))
        with pytest.raises(DidwwNotFoundError) as caught:
            client._execute(
                RequestSpec("GET", f"{API_PREFIX}/applications/nope", None),
                self._decode_application,
            )
        assert caught.value.codes == ("not_found",)

    def test_it_inherits_read_retry(self) -> None:
        attempts: list[int] = []

        def handler(_request: httpx2.Request) -> httpx2.Response:
            attempts.append(1)
            if len(attempts) == 1:
                return httpx2.Response(503, content=b"")
            return httpx2.Response(200, json={"data": {"id": "app-1", "name": "Checkout"}})

        client = client_with(httpx2.MockTransport(handler))
        result = client._execute(
            RequestSpec("GET", f"{API_PREFIX}/applications/app-1", None),
            self._decode_application,
        )
        assert len(attempts) == 2
        assert result.name == "Checkout"


class TestACollectionEndpointDecodes:
    """`logs`-shaped responses: ``data`` is an array. The driver, the signer and the
    error mapping are the same ones the single-resource endpoints use."""

    @dataclass(frozen=True, slots=True)
    class LogEntry:
        id: str
        status: str

    @classmethod
    def _decode_logs(cls, outcome: Outcome) -> list[LogEntry]:
        return [
            cls.LogEntry(id=str(row["id"]), status=str(row["status"]))
            for row in data_list_of(outcome)
        ]

    @staticmethod
    def _serving(payload: object) -> httpx2.MockTransport:
        return httpx2.MockTransport(lambda _r: httpx2.Response(200, json=payload))

    def test_a_collection_decodes_through_the_same_driver(self) -> None:
        client = client_with(
            self._serving(
                {
                    "data": [
                        {"id": "log-1", "status": "delivered"},
                        {"id": "log-2", "status": "failed"},
                    ],
                    "meta": {"total": 2},
                }
            )
        )
        rows = client._execute(
            RequestSpec("GET", f"{API_PREFIX}/logs", None, {"page": "1", "per_page": "50"}),
            self._decode_logs,
        )
        assert rows == [
            self.LogEntry("log-1", "delivered"),
            self.LogEntry("log-2", "failed"),
        ]

    def test_an_empty_collection_is_not_an_error(self) -> None:
        client = client_with(self._serving({"data": [], "meta": {"total": 0}}))
        assert (
            client._execute(RequestSpec("GET", f"{API_PREFIX}/logs", None), self._decode_logs) == []
        )

    def test_sibling_envelope_keys_stay_reachable(self) -> None:
        """Pagination is undecided, so a decoder reads `meta` itself rather than
        going through a shape this SDK guessed."""
        client = client_with(self._serving({"data": [], "meta": {"total": 41, "page": 2}}))
        meta = client._execute(
            RequestSpec("GET", f"{API_PREFIX}/logs", None),
            lambda outcome: envelope_of(outcome).get("meta"),
        )
        assert meta == {"total": 41, "page": 2}

    def test_a_single_resource_shape_is_rejected_clearly(self) -> None:
        client = client_with(self._serving({"data": {"id": "log-1"}}))
        with pytest.raises(DidwwDecodingError, match="no 'data' array, got dict"):
            client._execute(RequestSpec("GET", f"{API_PREFIX}/logs", None), self._decode_logs)


class TestADeleteHasSomewhereToLand:
    """A delete answers 204 with no body, and DELETE is not one of the verbs the
    existing endpoints use. Both had to exist before an Applications-style resource
    could be added without touching the driver."""

    @staticmethod
    def _serving(status: int, body: bytes) -> httpx2.MockTransport:
        return httpx2.MockTransport(lambda _r: httpx2.Response(status, content=body))

    def test_delete_is_an_allowed_verb(self) -> None:
        transport, seen = recording_transport()
        client_with(transport)._execute(
            RequestSpec("DELETE", f"{API_PREFIX}/applications/a1", None), no_content
        )
        assert seen[0].method == "DELETE"

    def test_a_204_decodes_rather_than_raising(self) -> None:
        client = client_with(self._serving(204, b""))
        assert client._execute(RequestSpec("DELETE", f"{API_PREFIX}/x/1", None), no_content) is None

    def test_a_bodyless_delete_sends_no_content_type(self) -> None:
        transport, seen = recording_transport()
        client_with(transport)._execute(
            RequestSpec("DELETE", f"{API_PREFIX}/applications/a1", None), no_content
        )
        assert "content-type" not in seen[0].headers

    def test_a_delete_is_never_retried(self) -> None:
        calls: list[int] = []

        def handler(_r: httpx2.Request) -> httpx2.Response:
            calls.append(1)
            return httpx2.Response(503, content=b"")

        client = client_with(httpx2.MockTransport(handler))
        with pytest.raises(DidwwServerError):
            client._execute(RequestSpec("DELETE", f"{API_PREFIX}/x/1", None), no_content)
        assert len(calls) == 1

    def test_an_error_status_still_raises_with_its_codes(self) -> None:
        client = client_with(
            self._serving(404, json.dumps({"errors": [{"code": "not_found"}]}).encode())
        )
        with pytest.raises(DidwwNotFoundError) as caught:
            client._execute(RequestSpec("DELETE", f"{API_PREFIX}/x/1", None), no_content)
        assert caught.value.codes == ("not_found",)


class TestChannelOptionsReachTheWire:
    """`build_start` used to list each channel field by hand. Adding a field to the
    dataclass and forgetting that list produced a valid request with the option
    silently absent -- mypy clean, tests green, the service never told. The block is
    now built from the dataclass, so these pin the properties that makes true."""

    @staticmethod
    def _block(channel: str, options: SmsOptions | CalloutOptions) -> dict[str, object]:
        if isinstance(options, SmsOptions):
            spec = build_start(destination="+37112345678", delivery_method=channel, sms=options)
        else:
            spec = build_start(destination="+37112345678", delivery_method=channel, callout=options)
        assert spec.body is not None
        payload = cast("dict[str, Any]", json.loads(spec.body))
        return cast("dict[str, object]", payload["data"].get(channel))

    def test_every_declared_field_reaches_the_wire(self) -> None:
        """The regression itself: a field the serializer does not know about.

        Built reflectively on purpose. Listing the fields here would go stale the same
        way the serializer did, and stop guarding the thing it exists to guard.
        """
        for cls, channel in ((SmsOptions, "sms"), (CalloutOptions, "callout")):
            values: dict[str, Any] = {
                f.name: ["en-US"] if "Sequence" in str(f.type) else "v" for f in fields(cls)
            }
            populated = cls(**values)
            missing = {f.name for f in fields(cls)} - set(self._block(channel, populated))
            assert not missing, f"{cls.__name__} fields dropped before the wire: {sorted(missing)}"

    def test_unset_fields_are_omitted_not_nulled(self) -> None:
        assert self._block("sms", SmsOptions(app_hash="abc")) == {"app_hash": "abc"}

    def test_options_with_nothing_set_send_an_empty_block(self) -> None:
        assert self._block("sms", SmsOptions()) == {}

    def test_a_sequence_that_is_not_a_list_is_coerced(self) -> None:
        """``Sequence[str]`` admits more than list. A tuple survives json.dumps; a
        range does not, so the block must coerce rather than pass through."""
        assert self._block("sms", SmsOptions(languages=("en-US", "pl-PL")))["languages"] == [
            "en-US",
            "pl-PL",
        ]
        odd: Any = range(0)
        assert self._block("callout", CalloutOptions(languages=odd))["languages"] == []

    def test_a_string_is_never_exploded_into_characters(self) -> None:
        """str is a Sequence. Coercing it would send ["a","b","c"]."""
        assert self._block("sms", SmsOptions(app_hash="abc"))["app_hash"] == "abc"

    def test_both_blocks_may_travel_together(self) -> None:
        spec = build_start(
            destination="+37112345678",
            delivery_method="sms",
            sms=SmsOptions(languages=["en-US"]),
            callout=CalloutOptions(languages=["pl-PL"]),
        )
        assert spec.body is not None
        data = cast("dict[str, Any]", json.loads(spec.body))["data"]
        assert data["sms"] == {"languages": ["en-US"]}
        assert data["callout"] == {"languages": ["pl-PL"]}
