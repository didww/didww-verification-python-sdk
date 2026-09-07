# Contributing

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Before opening a pull request:

```sh
ruff check . && ruff format --check .
mypy
pyright
pytest
```

All four must pass. They check different things: `mypy` treats a `Literal[...] | str` alias as
interchangeable with bare `str`, so the assertions in `tests/typing/` are meaningful only under
`pyright`.

## Adding an endpoint or an entity

Four local edits. Nothing in the driver, the signer or the error mapping should need to change
— if it does, say so in the pull request, because that is a structural change and not a
routine one.

1. **A builder** in `_requests.py` returning a `RequestSpec`. Give it the path and, for a write,
   a body through `_encode`. Query parameters go in `RequestSpec.query`; they are excluded from
   the signature, as the service excludes them.
2. **A decoder** in `_responses.py` with the shape `(Outcome) -> YourEntity`. Start from one of
   three entry points — all three have already raised for a transport fault, a non-2xx and an
   unreadable body:

   | Response shape | Entry point |
   |---|---|
   | `{"data": {...}}` — one resource | `data_of(outcome)` |
   | `{"data": [...]}` — a collection | `data_list_of(outcome)` |
   | `204`, or a body worth ignoring | `no_content` — pass it directly, write no decoder |
   | needs a sibling key such as `meta` | `envelope_of(outcome)` |

   Read fields with `_required_str`, `_optional_str`, `_optional_decimal` and
   `_optional_timestamp`. Decode fail-open: an unrecognised enum value keeps its raw string.

   **Pagination is deliberately unmodelled.** No endpoint returns a collection yet, so its
   envelope is undecided; read `meta` yourself rather than inheriting a shape this SDK guessed
   before the API had one.
3. **A frozen dataclass** in `models.py`, `slots=True`, exported from `__init__.py`.
4. **A method on each client**, sync and async. Reads go through `_execute(spec, decoder)`;
   Verification reads use the `_verify(spec)` lane. Retry is automatic for `GET` and must stay
   off for anything that charges, supersedes, or consumes an attempt.

   **Methods are flat, named `<verb>_<resource>`** — `get_application`, `create_application`,
   `delete_application`, with `_by_<key>` and `_raw` as suffixes where they apply. Not
   `client.applications.get()`. Resource namespaces read better past roughly five resources,
   but adopting them later renames every existing method, so the choice was made once, before
   publication, and applies to everything added since.

`tests/test_extension_seams.py` holds these guarantees. It decodes an entity that does not
exist in the SDK, through the real driver, to prove a new one needs no driver change.

## What tests are for here

This SDK signs its requests, and a signing bug is self-consistent: the client and the signer
agree with each other and disagree only with the service. A test that compares them therefore
passes while every real request fails.

So the signing tests use vectors that come from the service, and the transport tests assert on
the built request -- its headers, its raw path, its bytes -- rather than on a round trip. When
you add a test in that area, make sure it could actually fail.
