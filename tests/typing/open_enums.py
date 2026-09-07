"""Static proofs about the open-enum scheme. Checked by pyright, not by pytest.

These are gated on pyright deliberately. mypy treats a ``Literal[...] | str`` alias
as interchangeable with bare ``str`` in *both* directions, so every assertion below
would pass under mypy even if the aliases were plain ``str`` -- proving nothing.
pyright distinguishes them, which is what makes these assertions mean something.

Nothing here runs. The file is deliberately not named ``test_*`` so pytest never
collects it -- these are assertions about types, and there is nothing to execute.
"""

from __future__ import annotations

# typing.assert_type is 3.11+; the supported floor is 3.10.
from typing_extensions import assert_type

from didww_verification import (
    DeliveryMethod,
    KnownDeliveryMethod,
    VerificationStatus,
    is_known_delivery_method,
)


def writes_are_closed(method: KnownDeliveryMethod) -> None:
    """A channel the service does not know is a request that fails, so writes are closed."""


def check_a_known_channel_is_accepted() -> None:
    writes_are_closed("sms")
    writes_are_closed("callout")


def check_an_unknown_channel_is_rejected_at_the_write_boundary() -> None:
    writes_are_closed("some_new_channel")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def check_a_decoded_value_cannot_be_written_without_narrowing(decoded: DeliveryMethod) -> None:
    """The open alias is not silently assignable to the closed one."""
    writes_are_closed(decoded)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def check_the_guard_narrows_the_open_alias_to_the_closed_one(decoded: DeliveryMethod) -> None:
    if is_known_delivery_method(decoded):
        assert_type(decoded, KnownDeliveryMethod)
        writes_are_closed(decoded)


def check_the_open_alias_keeps_its_members(decoded: DeliveryMethod) -> None:
    """Not collapsed to bare ``str``: the literal members survive for completion."""
    assert_type(decoded, DeliveryMethod)


def check_a_decoded_status_is_open(status: VerificationStatus) -> None:
    """A status added after this release decodes as a plain string rather than raising."""
    assert_type(status, VerificationStatus)
