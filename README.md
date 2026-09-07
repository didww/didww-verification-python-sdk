# DIDWW Verification SDK for Python

Python client for the [DIDWW](https://www.didww.com/) Verification API: start a phone
verification, report the code the user entered, and read the outcome. Ships a
synchronous and an asynchronous client, and a callback verifier that needs no HTTP
client at all.

- Python 3.10+
- Fully typed, `py.typed` included
- One runtime dependency (`httpx2`) plus `anyio`

## Installation

```sh
pip install didww-verification
```

## Quick start

```python
from didww_verification import BasicAuth, VerificationClient

with VerificationClient(BasicAuth(key, secret)) as client:
    verification = client.start_verification(
        destination="+37112345678",
        delivery_method="sms",
    )

    # The code arrives by SMS; ask the user for it, then report it.
    verification = client.report_verification(verification.id, delivery_method="sms", code="123456")

    print(verification.status)  # "verified", "failed", ...
```

Async is the same surface with `await`:

```python
from didww_verification import AsyncVerificationClient, BasicAuth

async with AsyncVerificationClient(BasicAuth(key, secret)) as client:
    verification = await client.start_verification(
        destination="+37112345678", delivery_method="sms"
    )
```

Both clients build, sign and decode through the same code and put identical bytes on
the wire.

## Outcomes are data, not exceptions

A verification that ends `failed`, `expired` or `denied` is a **successful** API
call. Read the result rather than catching something:

```python
verification = client.get_verification(verification_id)

if verification.status == "verified":
    grant_access()
elif verification.is_finished:
    # error_code says why: too_many_attempts, expired, superseded, ...
    show(verification.error_detail)
else:
    keep_polling()
```

`is_finished` is the signal to stop polling. Statuses and error codes are an open
set: one added after this release arrives as a plain string rather than raising, so
compare against `is_known_verification_status` before switching exhaustively.

Only transport faults, non-2xx responses and unreadable bodies raise — see
[Errors](#errors).

## Addressing a verification by phone number

When the id was never persisted, every read and report has a `by_number` twin:

```python
client.get_verification_by_number("+37112345678")
client.report_verification_by_number("+37112345678", delivery_method="sms", code="123456")
```

"By number" resolves to the **newest** verification for that number, finished ones
included. One caveat worth designing around: a start that is itself denied does not
supersede an earlier live verification, so a `by_number` read can return the denied
row while the live one is reachable only by its id. Hold the id from the start
response when you can.

## Per-channel options

Options travel in a block named after the channel. Only the block matching
`delivery_method` is read.

```python
from didww_verification import CalloutOptions, SmsOptions

client.start_verification(
    destination="+37112345678",
    delivery_method="sms",
    sms=SmsOptions(languages=["lv-LV", "en-US"]),
)

client.start_verification(
    destination="+37112345678",
    delivery_method="callout",
    callout=CalloutOptions(languages=["de-DE"]),
)
```

Languages are BCP 47 tags, tried in order, falling back to `en-US`. **Send the region
subtag.** A bare primary subtag like `pl` passes validation and then silently falls
back, because the catalogue is matched on the exact canonical tag.

The response reports the tag actually used, so a fallback is detected rather than
guessed at:

```python
verification.sms.language  # the tag the message was rendered in
verification.callout.language  # the tag the announcement is played in
```

The two catalogues are separate: a tag with an SMS template may still have no
recording.

## Environments

```python
from didww_verification import Environment, VerificationClient

VerificationClient(auth, environment=Environment.SANDBOX)
VerificationClient(auth, base_url="http://localhost:3000")  # an origin, no path
```

`base_url` must be an origin. The SDK adds its own `/api/v1` prefix, and a base URL
that already contains it produces a doubled path.

## Authentication

Three schemes, ranked `public < basic < application`. Each application has a minimum;
anything below it is rejected with 401.

```python
from didww_verification import ApplicationAuth, BasicAuth, PublicAuth

PublicAuth(key)  # Authorization: Application <key>
BasicAuth(key, secret)  # Authorization: Basic base64(key:secret)
ApplicationAuth(key, secret)  # HMAC-signed, plus an x-timestamp header
```

- **`PublicAuth`** carries no secret. The key identifies rather than authenticates, so
  it is safe in a client users can read. What authorises a start is your registered
  callback URL — with none registered, a start under this scheme is denied outright.
- **`BasicAuth`** is server-to-server only; the secret is recoverable from anything
  that ships it.
- **`ApplicationAuth`** signs every request. It is the only scheme whose starts skip
  the outbound callback, since a signed caller is already trusted. A malformed secret
  fails at construction rather than on the first request.

Every authentication failure — unknown key, wrong secret, bad signature, stale
timestamp, too weak a scheme — answers 401 with no further detail, by design.

## Verifying inbound callbacks

Before creating a verification, the API can call your registered callback URL and wait
for you to allow or deny it. There is **one request and no retry**: whatever you
answer decides the verification.

```python
from didww_verification.callback import CallbackVerifier, allow, deny

verifier = CallbackVerifier(
    secret=application_secret,
    callback_url="https://example.com/callbacks/didww",  # as registered, verbatim
)
```

`callback_url` must be the URL **registered with DIDWW**, not the path the request
arrives on — an ingress that rewrites, or an app mounted under a prefix, makes these
differ. Two consequences:

- A registered URL with no path — `https://example.com` — signs the **empty string**,
  not `/`. A verifier that defaults to the received pathname computes a valid
  signature over `/` and then denies every verification, with correct code on both
  sides.
- `https://example.com` and `https://example.com/` are different signatures. Do not
  normalise the trailing slash.

Importing `didww_verification.callback` pulls in no HTTP client, so a service that
only receives callbacks pays nothing for one.

### FastAPI / Starlette

```python
from fastapi import Request, Response
from didww_verification.callback import allow, deny
from didww_verification.callback.fastapi import verify_request


@app.post("/callbacks/didww")
async def didww_callback(request: Request) -> Response:
    if not await verify_request(verifier, request):
        return Response(status_code=401)

    payload = await request.json()
    body = allow() if is_expected(payload) else deny()
    return Response(body, media_type="application/json")
```

### Django

```python
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from didww_verification.callback import allow, deny
from didww_verification.callback.django import verify_request


@csrf_exempt
def didww_callback(request):
    if not verify_request(verifier, request):
        return HttpResponse(status=401)
    return HttpResponse(allow(), content_type="application/json")
```

The view must be CSRF-exempt: the request comes from DIDWW, not from a form, and
carries its own signature.

### Any other framework

Pass the pieces yourself. `body` must be the **received bytes** — re-serializing
parsed parameters changes them and the signature will not match:

```python
verifier.is_valid(
    method=request.method,
    content_type=request.content_type,
    body=raw_body,
    timestamp=request.headers.get("x-timestamp"),
    signature=signature,  # from parse_authorization(...)
)
```

Answer with `allow()` or `deny()` and nothing else. Never echo *why* a request failed:
that distinguishes an unknown key from a bad signature, which turns your endpoint into
an oracle for which application keys exist.

## Errors

```python
from didww_verification import DidwwApiError, DidwwValidationError

try:
    client.start_verification(destination=number, delivery_method="sms")
except DidwwValidationError as exc:
    if exc.has_code("destination_invalid"):
        ...
except DidwwApiError as exc:
    log.warning("didww: %s %s", exc.status, exc.codes)
```

| Exception | When |
| --- | --- |
| `DidwwUnauthorizedError` | 401 |
| `DidwwBalanceInsufficientError` | 402 |
| `DidwwNotFoundError` | 404 |
| `DidwwValidationError` | 400, 422 |
| `DidwwServerError` | 5xx |
| `DidwwApiError` | any other non-2xx; base class of the above |
| `DidwwTransportError` | no response: connect, timeout, TLS |
| `DidwwDecodingError` | a 2xx body this SDK could not read |
| `DidwwConfigurationError` | a bad secret or an unusable base URL |

All descend from `DidwwVerificationError`. One response can carry several errors — a
validation failure returns one per field — so use `codes` and `has_code`, not
`errors[0]`. `code` is a stable slug to switch on; `detail` is fixed prose to display,
never to parse.

A non-2xx whose body is not JSON still raises the status-mapped error with empty
`errors`, so an error page from a proxy surfaces as the server error it is.

## Retries

Only reads are retried, on transport faults and 5xx, twice by default:

```python
from didww_verification import RetryPolicy

VerificationClient(auth, retry=RetryPolicy(attempts=3, base_delay=0.5))
VerificationClient(auth, retry=RetryPolicy(attempts=1))  # off
```

Starts and reports are **never** retried, and you should not add it. The API has no
idempotency key: a repeated start supersedes the live verification and charges again,
and a repeated report consumes one of three attempts. Exceeding that limit is answered
with a normal 200 whose status is `failed` — read the result rather than counting
attempts yourself.

## A channel this release does not model

`delivery_method` is an open vocabulary on read. If a verification you can read
reports a channel outside `DELIVERY_METHODS`, report it with the raw variant, which
performs no client-side check:

```python
client.report_verification_raw(
    verification.id, delivery_method=verification.delivery_method, code=value
)
```

## Development

```sh
pip install -e ".[dev]"
pytest
ruff check . && mypy && pyright
```
