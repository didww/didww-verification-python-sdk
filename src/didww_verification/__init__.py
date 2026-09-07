"""Python SDK for the DIDWW Verification API.

Start a verification, report the code the user entered, and read the outcome::

    from didww_verification import BasicAuth, VerificationClient

    with VerificationClient(BasicAuth(key, secret)) as client:
        v = client.start_verification(destination="+37112345678", delivery_method="sms")
        v = client.report_verification(v.id, delivery_method="sms", code="123456")
        print(v.status)

An outcome is data, not an exception: a verification that ends ``failed``, ``expired``
or ``denied`` comes back as a :class:`Verification` with ``status`` and ``error_code``
set. Only a non-2xx, a transport fault or an unreadable body raises.

:class:`AsyncVerificationClient` is the same surface with ``await``. Inbound callbacks
are verified via :mod:`didww_verification.callback`, which imports no HTTP client.
"""

from ._version import VERSION as __version__
from .async_client import AsyncVerificationClient
from .auth import ApplicationAuth, Auth, BasicAuth, PublicAuth
from .client import VerificationClient
from .config import Environment, RetryPolicy
from .errors import (
    DidwwApiError,
    DidwwBalanceInsufficientError,
    DidwwConfigurationError,
    DidwwDecodingError,
    DidwwNotFoundError,
    DidwwServerError,
    DidwwTransportError,
    DidwwUnauthorizedError,
    DidwwValidationError,
    DidwwVerificationError,
    ErrorItem,
)
from .models import CalloutInfo, CalloutOptions, SmsInfo, SmsOptions, Verification
from .vocabulary import (
    API_ERROR_CODES,
    DELIVERY_METHODS,
    VERIFICATION_ERROR_CODES,
    VERIFICATION_STATUSES,
    ApiErrorCode,
    DeliveryMethod,
    KnownApiErrorCode,
    KnownDeliveryMethod,
    KnownVerificationErrorCode,
    KnownVerificationStatus,
    VerificationErrorCode,
    VerificationStatus,
    is_known_api_error_code,
    is_known_delivery_method,
    is_known_verification_error_code,
    is_known_verification_status,
)

__all__ = [
    "API_ERROR_CODES",
    "DELIVERY_METHODS",
    "VERIFICATION_ERROR_CODES",
    "VERIFICATION_STATUSES",
    "ApiErrorCode",
    "ApplicationAuth",
    "AsyncVerificationClient",
    "Auth",
    "BasicAuth",
    "CalloutInfo",
    "CalloutOptions",
    "DeliveryMethod",
    "DidwwApiError",
    "DidwwBalanceInsufficientError",
    "DidwwConfigurationError",
    "DidwwDecodingError",
    "DidwwNotFoundError",
    "DidwwServerError",
    "DidwwTransportError",
    "DidwwUnauthorizedError",
    "DidwwValidationError",
    "DidwwVerificationError",
    "Environment",
    "ErrorItem",
    "KnownApiErrorCode",
    "KnownDeliveryMethod",
    "KnownVerificationErrorCode",
    "KnownVerificationStatus",
    "PublicAuth",
    "RetryPolicy",
    "SmsInfo",
    "SmsOptions",
    "Verification",
    "VerificationClient",
    "VerificationErrorCode",
    "VerificationStatus",
    "__version__",
    "is_known_api_error_code",
    "is_known_delivery_method",
    "is_known_verification_error_code",
    "is_known_verification_status",
]
