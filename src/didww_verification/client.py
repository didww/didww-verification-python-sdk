"""The synchronous client."""

from __future__ import annotations

import time
from collections.abc import Callable
from types import TracebackType
from typing import Any, TypeVar

import httpx2

from . import _requests as rq
from ._responses import HttpOutcome, Outcome, TransportFailure, decode_verification
from ._retry import delay_for, is_retryable
from .auth import Auth
from .config import DEFAULT_USER_AGENT, Environment, RetryPolicy, validate_base_url
from .models import CalloutOptions, SmsOptions, Verification
from .vocabulary import KnownDeliveryMethod

__all__ = ["VerificationClient"]

T = TypeVar("T")


class VerificationClient:
    """A synchronous client for the DIDWW Verification API.

    Use it as a context manager, or call :meth:`close` when done::

        with VerificationClient(BasicAuth(key, secret)) as client:
            v = client.start_verification(destination="+37112345678", delivery_method="sms")

    Every method returns a :class:`Verification` or raises. A verification that ends
    badly is *not* an exception: check ``status`` and ``error_code``.

    :class:`didww_verification.async_client.AsyncVerificationClient` is the same
    surface with ``await``, over the same build/sign/decode code.
    """

    def __init__(
        self,
        auth: Auth,
        *,
        environment: Environment = Environment.PRODUCTION,
        base_url: str | None = None,
        timeout: float = 30.0,
        retry: RetryPolicy | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        keep_raw_payload: bool = False,
        http_client: httpx2.Client | None = None,
    ) -> None:
        """
        :param base_url: an origin, overriding ``environment``. Must carry no path.
        :param retry: read-retry policy. Writes are never retried.
        :param keep_raw_payload: retain the decoded envelope on each Verification.
            Off by default; it keeps the destination in memory and is not covered by
            semantic versioning.
        :param http_client: bring your own client for proxies, TLS or connection
            limits. It is *not* closed by this client, since you own its lifetime.
        """
        self._auth = auth
        self._base_url = validate_base_url(base_url or environment.value)
        self._retry = retry or RetryPolicy()
        self._keep_raw = keep_raw_payload
        self._owns_client = http_client is None
        self._http = http_client or httpx2.Client(timeout=timeout)
        self._http.base_url = httpx2.URL(self._base_url)
        self._http.headers["user-agent"] = user_agent

    def close(self) -> None:
        """Close the underlying connection pool, unless you supplied the client."""
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> VerificationClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def start_verification(
        self,
        *,
        destination: str,
        delivery_method: KnownDeliveryMethod,
        sms: SmsOptions | None = None,
        callout: CalloutOptions | None = None,
    ) -> Verification:
        """Start a verification. Never retried: a repeat supersedes and charges again."""
        return self._verify(
            rq.build_start(
                destination=destination,
                delivery_method=delivery_method,
                sms=sms,
                callout=callout,
            )
        )

    def get_verification(self, verification_id: str) -> Verification:
        """Read a verification by id."""
        return self._verify(rq.build_get(verification_id))

    def report_verification(
        self, verification_id: str, *, delivery_method: KnownDeliveryMethod, code: str
    ) -> Verification:
        """Report the code the user entered.

        Consumes one of a small number of attempts, so this is never retried. Exceeding
        the limit is a normal 200 with status ``failed``, not an error.
        """
        return self._verify(
            rq.build_report(verification_id, delivery_method=delivery_method, code=code)
        )

    def get_verification_by_number(self, number: str) -> Verification:
        """Read the newest verification for a number, finished ones included."""
        return self._verify(rq.build_get_by_number(number))

    def report_verification_by_number(
        self, number: str, *, delivery_method: KnownDeliveryMethod, code: str
    ) -> Verification:
        """Report against the newest verification for a number."""
        return self._verify(
            rq.build_report_by_number(number, delivery_method=delivery_method, code=code)
        )

    def report_verification_raw(
        self, verification_id: str, *, delivery_method: str, code: str
    ) -> Verification:
        """Report against a verification whose channel this release does not model.

        ``delivery_method`` is an open string and no client-side check runs. Reach for
        it when a verification you can read reports a method outside ``DELIVERY_METHODS``.
        """
        return self._verify(
            rq.build_report(verification_id, delivery_method=delivery_method, code=code)
        )

    def report_verification_by_number_raw(
        self, number: str, *, delivery_method: str, code: str
    ) -> Verification:
        """:meth:`report_verification_raw`, addressed by number."""
        return self._verify(
            rq.build_report_by_number(number, delivery_method=delivery_method, code=code)
        )

    def _decode(self, outcome: Outcome) -> Verification:
        return decode_verification(outcome, keep_raw_payload=self._keep_raw)

    def _verify(self, spec: rq.RequestSpec) -> Verification:
        """Run ``spec`` and decode a Verification. The lane every endpoint here uses."""
        return self._execute(spec, self._decode)

    def _execute(self, spec: rq.RequestSpec, decode: Callable[[Outcome], T]) -> T:
        """Send, retrying reads, and decode.

        The only place in the SDK that performs I/O or sleeps; everything it calls is
        pure. Generic over ``decode`` so a new entity needs a decoder, not a new driver.
        """
        attempts = self._retry.attempts if spec.method == "GET" else 1
        outcome: Outcome
        for attempt in range(1, attempts + 1):
            kwargs: dict[str, Any] = {}
            if spec.body is not None:
                kwargs["content"] = spec.body
                kwargs["headers"] = {"content-type": "application/json"}
            if spec.query is not None:
                kwargs["params"] = dict(spec.query)
            request = self._http.build_request(spec.method, spec.path, **kwargs)
            # Re-signed per attempt: a stale timestamp falls outside the replay window.
            rq.apply_auth(request, self._auth, self._retry.clock())
            try:
                response = self._http.send(request)
            except httpx2.HTTPError as exc:
                outcome = TransportFailure(exc)
            else:
                outcome = HttpOutcome(response.status_code, response.content)
            if attempt < attempts and is_retryable(outcome):
                time.sleep(delay_for(attempt, self._retry.base_delay, self._retry.rand()))
                continue
            return decode(outcome)
        raise AssertionError("unreachable")  # pragma: no cover
