# Changelog

Notable changes to the DIDWW Verification SDK for Python.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
