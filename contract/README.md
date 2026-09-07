# contract/

`wire_contract.json` is a snapshot of the API this SDK speaks to: its routes, its
vocabularies, and the rules the SDK cannot discover at runtime.

It exists so that drift is **detectable**. Nothing in this repository can tell you
whether the SDK still matches the service — only a comparison against the service
can. The snapshot is one half of that comparison; `capturedAt` says when it was
taken.

The test suite asserts that the SDK's exported vocabularies equal this file's. That
catches a vocabulary edit that forgets the snapshot, but it cannot catch the two of
them being wrong together. For that, re-capture the snapshot from the service at
release time and read the diff.

Re-capture it from the service, never from another client library. A client library is
itself a snapshot taken at some earlier moment, so seeding from one imports whatever
drift it has accumulated since — silently, and dated as if it were current.
