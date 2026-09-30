"""The objects the API returns, and the options it accepts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from warnings import warn

from .vocabulary import DeliveryMethod, VerificationErrorCode, VerificationStatus

__all__ = ["Autofill", "CalloutInfo", "CalloutOptions", "SmsInfo", "SmsOptions", "Verification"]


@dataclass(frozen=True, slots=True)
class Autofill:
    """How the SMS is framed for the device's autofill.

    ``type`` is an open string so a type the service adds later needs no new release
    to be read back. Build one with :meth:`app_hash` or :meth:`none`.
    """

    type: str
    value: str | None = None

    @classmethod
    def app_hash(cls, value: str) -> Autofill:
        """Android SMS Retriever framing for the 11-character app hash ``value``."""
        return cls("app_hash", value)

    @classmethod
    def none(cls) -> Autofill:
        """No marker, regardless of the application default."""
        return cls("none")


@dataclass(frozen=True, slots=True)
class SmsOptions:
    """Options for an SMS start.

    ``languages`` are BCP 47 tags, tried in order. Template lookup is an exact match on
    the canonical tag, so a bare ``pl`` passes validation and then silently falls back
    -- send ``pl-PL``. Rejecting a region-less tag here would refuse what the service
    accepts.

    ``app_hash`` is deprecated: pass ``autofill=Autofill.app_hash(...)`` instead. It is
    folded into ``autofill`` on construction, and a conflicting ``autofill`` raises
    ``ValueError``.
    """

    languages: Sequence[str] | None = None
    app_hash: str | None = None
    autofill: Autofill | None = None

    def __post_init__(self) -> None:
        if self.app_hash is None:
            return
        derived = Autofill.app_hash(self.app_hash)
        if self.autofill is None:
            warn(
                "SmsOptions(app_hash=...) is deprecated; use autofill=Autofill.app_hash(...)",
                DeprecationWarning,
                stacklevel=3,
            )
            # Frozen: fold the alias in place. app_hash stays readable but never travels.
            object.__setattr__(self, "autofill", derived)
        elif self.autofill != derived:
            raise ValueError("pass either autofill or the deprecated app_hash, not both")


@dataclass(frozen=True, slots=True)
class CalloutOptions:
    """Options for a callout start.

    Same tag rules as :class:`SmsOptions`, resolved against a different catalogue, so
    one list can resolve differently per channel.
    """

    languages: Sequence[str] | None = None


@dataclass(frozen=True, slots=True)
class SmsInfo:
    """The ``sms`` block, present only when the delivery method is ``sms``."""

    template: str | None
    language: str | None
    interception_timeout: int | None
    """Seconds the SMS Retriever stays armed for. Equal to the application's
    configured code lifetime (60-600, default 300), not a fixed window."""
    app_hash: str | None
    """Deprecated: ``autofill.value`` when ``autofill.type`` is ``app_hash``, else
    ``None``. The service no longer returns this field itself."""
    code_length: int
    """The generated code's length, 4-8."""
    autofill: Autofill | None = None
    """Echoed back only when a hash was stored. Equality with what you sent is the
    only confirmation it was accepted."""


@dataclass(frozen=True, slots=True)
class CalloutInfo:
    """The ``callout`` block, present only when the delivery method is ``callout``."""

    language: str | None
    code_length: int
    """The generated code's length, 4-8."""


@dataclass(frozen=True, slots=True)
class Verification:
    """One verification, as returned by every endpoint.

    ``status`` and ``error_code`` are open vocabularies: a value added after this
    release arrives as a plain string rather than raising.
    """

    id: str
    destination: str
    delivery_method: DeliveryMethod
    fee: Decimal | None
    status: VerificationStatus
    error_code: VerificationErrorCode | None
    error_detail: str | None
    expires_at: datetime | None
    """When the code stops being acceptable: creation time plus the application's
    configured code lifetime (60-600s, default 300), not a fixed window."""
    sms: SmsInfo | None
    callout: CalloutInfo | None
    raw: Mapping[str, Any] | None = field(default=None, compare=False, hash=False, repr=False)
    """The decoded ``data`` envelope, kept only when the client was built with
    ``keep_raw_payload=True``.

    Off by default: it pins the destination and the delivery metadata in memory for
    as long as the object lives. Excluded from equality and hashing -- a mapping is
    unhashable, and a frozen dataclass that advertises hashability must stay
    hashable. Not covered by semantic versioning.
    """

    @property
    def is_finished(self) -> bool:
        """True once the verification reached a terminal state -- stop polling.

        Derived from ``status`` rather than listing terminal states, so a status
        added after this release is treated as finished rather than polled forever.
        """
        return self.status != "pending"
