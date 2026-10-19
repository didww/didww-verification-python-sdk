"""The API's wire vocabulary: delivery methods, statuses, autofill types, template
fallback reasons and coded error slugs.

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
    "AUTOFILL_TYPES",
    "DELIVERY_METHODS",
    "TEMPLATE_FALLBACK_REASONS",
    "VERIFICATION_ERROR_CODES",
    "VERIFICATION_STATUSES",
    "ApiErrorCode",
    "AutofillType",
    "DeliveryMethod",
    "KnownApiErrorCode",
    "KnownAutofillType",
    "KnownDeliveryMethod",
    "KnownTemplateFallbackReason",
    "KnownVerificationErrorCode",
    "KnownVerificationStatus",
    "TemplateFallbackReason",
    "VerificationErrorCode",
    "VerificationStatus",
    "is_known_api_error_code",
    "is_known_autofill_type",
    "is_known_delivery_method",
    "is_known_template_fallback_reason",
    "is_known_verification_error_code",
    "is_known_verification_status",
]

DELIVERY_METHODS: Final = ("sms", "callout")

AUTOFILL_TYPES: Final = ("app_hash", "domain", "none")

VERIFICATION_STATUSES: Final = (
    "pending",
    "verified",
    "failed",
    "expired",
    "denied",
)

#: Why a group's template was not used. ``group_missing``: the group no longer exists.
TEMPLATE_FALLBACK_REASONS: Final = (
    "language_missing",
    "version_pending",
    "version_rejected",
    "audio_not_ready",
    "group_missing",
)

#: Codes that arrive as ``Verification.error_code`` on a finished verification. An
#: outcome is a success response, not an error, but they are included in
#: ``API_ERROR_CODES`` so one set covers every coded error.
#: ``destination_not_supported_for_channel`` is also kept as an envelope code for
#: compatibility.
#: ``stale_dispatch`` is deprecated: the service no longer sends it and reports
#: ``dispatch_failed`` instead.
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
    "application_paused",
    "destination_country_disabled",
    "destination_not_supported_for_channel",
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
    "autofill_invalid",
    "app_hash_invalid",
    "custom_too_long",
    "template_group_not_found",
    "sms_domain_not_configured",
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
    "destination_in_cooldown",
    "rate_limit_per_ip",
    "rate_limit_failed_auth",
    "rate_limit_per_account",
    "rate_limit_public_per_account",
    "volume_limit_reached",
    # Kept as an envelope code for compatibility, so listed once, above.
    *(c for c in VERIFICATION_ERROR_CODES if c != "destination_not_supported_for_channel"),
)

KnownDeliveryMethod: TypeAlias = Literal["sms", "callout"]
KnownAutofillType: TypeAlias = Literal["app_hash", "domain", "none"]
KnownVerificationStatus: TypeAlias = Literal["pending", "verified", "failed", "expired", "denied"]
KnownTemplateFallbackReason: TypeAlias = Literal[
    "language_missing",
    "version_pending",
    "version_rejected",
    "audio_not_ready",
    "group_missing",
]
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
    "application_paused",
    "destination_country_disabled",
    "destination_not_supported_for_channel",
]
KnownApiErrorCode: TypeAlias = Literal[
    "destination_blank",
    "destination_invalid",
    "delivery_method_blank",
    "delivery_method_inclusion",
    "delivery_method_invalid",
    "languages_invalid",
    "autofill_invalid",
    "app_hash_invalid",
    "custom_too_long",
    "template_group_not_found",
    "sms_domain_not_configured",
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
    "destination_in_cooldown",
    "rate_limit_per_ip",
    "rate_limit_failed_auth",
    "rate_limit_per_account",
    "rate_limit_public_per_account",
    "volume_limit_reached",
    "dispatch_failed",
    "expired",
    "too_many_attempts",
    "stale_dispatch",
    "application_deleted",
    "superseded",
    "denied_missing_callback_url",
    "denied_by_callback",
    "denied_invalid_callback_response",
    "application_paused",
    "destination_country_disabled",
]

#: Decoded. A value added after this release arrives as a new string, never as None.
DeliveryMethod: TypeAlias = KnownDeliveryMethod | str
AutofillType: TypeAlias = KnownAutofillType | str
VerificationStatus: TypeAlias = KnownVerificationStatus | str
TemplateFallbackReason: TypeAlias = KnownTemplateFallbackReason | str
VerificationErrorCode: TypeAlias = KnownVerificationErrorCode | str
ApiErrorCode: TypeAlias = KnownApiErrorCode | str


def is_known_delivery_method(value: str) -> TypeGuard[KnownDeliveryMethod]:
    """True when this release models the channel. Narrow before routing on it."""
    return value in DELIVERY_METHODS


def is_known_autofill_type(value: str) -> TypeGuard[KnownAutofillType]:
    """True when this release models the autofill type."""
    return value in AUTOFILL_TYPES


def is_known_verification_status(value: str) -> TypeGuard[KnownVerificationStatus]:
    """True when this release models the status."""
    return value in VERIFICATION_STATUSES


def is_known_template_fallback_reason(value: str) -> TypeGuard[KnownTemplateFallbackReason]:
    """True when this release models the fallback reason."""
    return value in TEMPLATE_FALLBACK_REASONS


def is_known_verification_error_code(
    value: str,
) -> TypeGuard[KnownVerificationErrorCode]:
    """True when this release models the outcome code."""
    return value in VERIFICATION_ERROR_CODES


def is_known_api_error_code(value: str) -> TypeGuard[KnownApiErrorCode]:
    """True when this release models the envelope code, so a match is exhaustive."""
    return value in API_ERROR_CODES
