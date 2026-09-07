"""The three authentication schemes, and what each is for."""

from __future__ import annotations

import os

from didww_verification import ApplicationAuth, BasicAuth, PublicAuth, VerificationClient

KEY = os.environ["DIDWW_KEY"]
SECRET = os.environ["DIDWW_SECRET"]

# Server-to-server. The secret is recoverable from anything that ships it.
basic = BasicAuth(KEY, SECRET)

# No secret: the key identifies, it does not authenticate. Your registered callback
# URL authorises each start; with none registered, a start here is denied.
public = PublicAuth(KEY)

# Signs every request, and the only scheme whose starts skip the outbound callback.
# A malformed secret fails here, not on the first request.
signed = ApplicationAuth(KEY, SECRET)

for name, auth in (("basic", basic), ("public", public), ("application", signed)):
    with VerificationClient(auth) as client:
        print(f"{name}: client ready")
