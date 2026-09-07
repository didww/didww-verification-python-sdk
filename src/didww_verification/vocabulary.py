"""The API's wire vocabulary: delivery methods, statuses and coded error slugs.

Two shapes per vocabulary. The ``Known*`` alias is a closed ``Literal`` and is what
the SDK *writes*. The bare alias is widened with ``| str`` and is what the SDK
*decodes*: a value added after this release arrives as a plain new string rather than
raising, and ``is_known_*`` narrows it back.

The tuples and the ``Literal`` aliases are two hand-maintained copies -- Python cannot
derive one from the other. They are asserted equal in the test suite: on drift a
``TypeGuard`` would narrow a value to a type it does not have, unnoticed.
"""

from typing import Final, Literal, TypeAlias, TypeGuard

__all__ = [
    "API_ERROR_CODES",
    "DELIVERY_METHODS",
    "VERIFICATION_ERROR_CODES",
    "VERIFICATION_STATUSES",
    "ApiErrorCode",
    "DeliveryMethod",
    "KnownApiErrorCode",
    "KnownDeliveryMethod",
    "KnownVerificationErrorCode",
    "KnownVerificationStatus",
    "VerificationErrorCode",
    "VerificationStatus",
    "is_known_api_error_code",
    "is_known_delivery_method",
    "is_known_verification_error_code",
    "is_known_verification_status",
]

DELIVERY_METHODS: Final = ("sms", "callout")

VERIFICATION_STATUSES: Final = (
    "pending",
    "verified",
    "failed",
    "expired",
    "denied",
)

#: Codes that arrive as ``Verification.error_code`` on a finished verification.
#: They never reach an error envelope -- an outcome is a 200, not an error -- but they
#: are included in ``API_ERROR_CODES`` so one set covers every coded error.
VERIFICATION_ERROR_CODES: Final = (
    "dispatch_failed",
    "expired",
    "too_many_attempts",
    "stale_dispatch",
    "application_deleted",
    "superseded",
    "denied_missing_callback_url",
    "denied_by_callback",
    "denied_invalid_callback_response",
)

#: Every coded error this API produces: the envelope codes first, then the outcome
#: codes, which reach you as ``Verification.error_code`` rather than in an envelope.
API_ERROR_CODES: Final = (
    "destination_blank",
    "destination_invalid",
    "delivery_method_blank",
    "delivery_method_inclusion",
    "delivery_method_invalid",
    "languages_invalid",
    "app_hash_invalid",
    "code_blank",
    "destination_not_supported_for_channel",
    "code_invalid",
    "already_verified",
    "not_ready_to_report",
    "parameter_missing",
    "not_found",
    "unauthorized",
    "balance_insufficient",
    "validation_failed",
    "internal_error",
    *VERIFICATION_ERROR_CODES,
)

KnownDeliveryMethod: TypeAlias = Literal["sms", "callout"]
KnownVerificationStatus: TypeAlias = Literal["pending", "verified", "failed", "expired", "denied"]
KnownVerificationErrorCode: TypeAlias = Literal[
    "dispatch_failed",
    "expired",
    "too_many_attempts",
    "stale_dispatch",
    "application_deleted",
    "superseded",
    "denied_missing_callback_url",
    "denied_by_callback",
    "denied_invalid_callback_response",
]
KnownApiErrorCode: TypeAlias = Literal[
    "destination_blank",
    "destination_invalid",
    "delivery_method_blank",
    "delivery_method_inclusion",
    "delivery_method_invalid",
    "languages_invalid",
    "app_hash_invalid",
    "code_blank",
    "destination_not_supported_for_channel",
    "code_invalid",
    "already_verified",
    "not_ready_to_report",
    "parameter_missing",
    "not_found",
    "unauthorized",
    "balance_insufficient",
    "validation_failed",
    "internal_error",
    "dispatch_failed",
    "expired",
    "too_many_attempts",
    "stale_dispatch",
    "application_deleted",
    "superseded",
    "denied_missing_callback_url",
    "denied_by_callback",
    "denied_invalid_callback_response",
]

#: Decoded. A value added after this release arrives as a new string, never as None.
DeliveryMethod: TypeAlias = KnownDeliveryMethod | str
VerificationStatus: TypeAlias = KnownVerificationStatus | str
VerificationErrorCode: TypeAlias = KnownVerificationErrorCode | str
ApiErrorCode: TypeAlias = KnownApiErrorCode | str


def is_known_delivery_method(value: str) -> TypeGuard[KnownDeliveryMethod]:
    """True when this release models the channel. Narrow before routing on it."""
    return value in DELIVERY_METHODS


def is_known_verification_status(value: str) -> TypeGuard[KnownVerificationStatus]:
    """True when this release models the status."""
    return value in VERIFICATION_STATUSES


def is_known_verification_error_code(
    value: str,
) -> TypeGuard[KnownVerificationErrorCode]:
    """True when this release models the outcome code."""
    return value in VERIFICATION_ERROR_CODES


def is_known_api_error_code(value: str) -> TypeGuard[KnownApiErrorCode]:
    """True when this release models the envelope code, so a match is exhaustive."""
    return value in API_ERROR_CODES
