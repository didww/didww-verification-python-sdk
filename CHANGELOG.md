# Changelog

Notable changes to the DIDWW Verification SDK for Python.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-10

### Added

- **`custom` on `start_verification`** (sync and async). Free text of up to 4096
  characters, delivered unchanged to your callback server as `data.custom`. It is not
  returned in any response. A longer value is refused with the new `custom_too_long`
  error code.

- **`SmsOptions.autofill`**, built with `Autofill.app_hash(value)`, `Autofill.domain()`
  or `Autofill.none()`. `SmsInfo.autofill` reads back the stored marker, `app_hash` or
  `domain`, whose `value` is the hash or the domain. `Autofill.type` is an open
  vocabulary (`AUTOFILL_TYPES`, `is_known_autofill_type`). New error codes
  `autofill_invalid` and `sms_domain_not_configured`.

- **`template_group` on `SmsOptions` and `CalloutOptions`**, to pick a template group
  instead of the application's default. `SmsInfo` and `CalloutInfo` gain
  `template_group`, `template_group_used` and `template_fallback_reason`, the last an
  open vocabulary (`TEMPLATE_FALLBACK_REASONS`, `is_known_template_fallback_reason`).
  An unknown group is refused with the new `template_group_not_found` error code.

- **`x-signature-previous` support in `CallbackVerifier`.** While an application secret is
  being rotated, callbacks also carry a signature made with the previous secret. The
  verifier takes it as the optional `previous_signature` argument to `check()` and
  `is_valid()` and accepts a callback when either signature matches the configured secret.
  The FastAPI and Django adapters pass the header through. Without the header, behaviour
  is unchanged.

- **New error codes for 429:** `rate_limit_per_ip`, `rate_limit_failed_auth`,
  `rate_limit_per_account`, `rate_limit_public_per_account`, and `volume_limit_reached`
  (the application reached its daily or monthly verification limit; `Retry-After` can
  be long, so surface it instead of retrying). All raise `DidwwRateLimitedError`.

- **New outcome codes:** `application_paused` and `destination_country_disabled`
  (status `denied`).

### Changed

- **An unsupported destination is no longer a 422.** A destination with no country, not
  supported for the delivery method, or in a blocked range now returns a 201
  verification with status `failed` and `error_code`
  `destination_not_supported_for_channel`. Code that handled the 422 must read the
  outcome instead. The code stays in the envelope vocabulary for compatibility.

- `SmsInfo` and `CalloutInfo` have three new required fields, so code that constructs
  them directly, for example in tests, must pass them.

### Deprecated

- **`SmsOptions(app_hash=...)` and `SmsInfo.app_hash`.** Use `autofill`. The alias is
  sent as `autofill=Autofill.app_hash(...)` and emits a `DeprecationWarning`; passing it
  with a different `autofill` raises `ValueError`.

- **The `stale_dispatch` outcome code.** The service no longer sends it and reports
  these verifications as `dispatch_failed`. It stays in the vocabulary so existing
  matches keep type-checking, and will be removed in the next major version.

### Docs

- A Testing section on the sandbox environment, which sends nothing and gives a
  predefined result only for the reserved test numbers.

## [1.1.0] — 2026-10

### Added

- **`code_length` on `SmsInfo` and `CalloutInfo`.** The generated code's length, 4–8.

- **`DidwwRateLimitedError`**, raised on 429 when a start is too soon after a
  non-denied one for the same destination (`destination_in_cooldown`). Carries
  `retry_after`, the wait in whole seconds when the response has a `Retry-After`
  header. Not auto-retried; wait `retry_after` and start again yourself.

### Changed

- `expires_at` and `sms.interception_timeout` reflect the application's configured
  code lifetime (60–600 seconds, default 300) rather than a fixed window.

- A 429 now raises `DidwwRateLimitedError`, a subclass of `DidwwApiError`, rather
  than the base class. `except DidwwApiError` still catches it; a strict
  `type(e) is DidwwApiError` check no longer matches.

### Deprecated

- **`user_agent`** on `VerificationClient` and `AsyncVerificationClient` is deprecated and
  ignored. The SDK always sends its own `User-Agent`; passing this parameter now emits a
  `DeprecationWarning` and will be removed in the next major version.

## [1.0.0] — 2026-09

First release.

### Added

- **Every verification endpoint, addressable two ways.** `start_verification`,
  `get_verification` and `report_verification` take an id; `get_verification_by_number` and
  `report_verification_by_number` take a phone number, for when the id was never persisted.

- **A synchronous and an asynchronous client.** Both build, sign and decode through the same
  code and are asserted to emit byte-identical requests; only where the request is sent and
  where the backoff sleeps differ between them.

- **All three authentication schemes**, modelled as distinct types rather than a mode string,
  so "public takes no secret" and "basic and application require one" are type errors rather
  than runtime validation. A malformed signing secret fails at construction.

- **The coded error envelope as typed exceptions**, carrying every error in the response
  rather than the first, with `codes` and `has_code`. A non-2xx whose body is not JSON still
  raises the status-mapped error, so an error page from a proxy is not reported as an SDK bug.

- **Outcomes as data.** A failed, expired or denied verification is a successful call:
  `status`, `error_code` and `error_detail` say what happened, and `is_finished` says when to
  stop polling.

- **Inbound callback verification**, with a five-minute replay window and constant-time
  comparison. Importing it loads no HTTP client. Adapters for FastAPI/Starlette and Django read
  the raw request body; neither framework is a runtime dependency.

- **Full typing**, `py.typed`, and open vocabularies that accept a value added after this
  release rather than raising on it.

### Notes

- Requires Python 3.10 or newer.
- Reads are retried on transport faults and 5xx. Starts and reports never are, and should not
  be: the API has no idempotency key, a repeated start supersedes and charges again, and a
  repeated report consumes one of three attempts.
