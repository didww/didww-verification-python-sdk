"""Poll a verification to its conclusion.

Shows the two rules that matter: stop on `is_finished` rather than on a list of
statuses you know today, and treat a bad outcome as data rather than an exception.
"""

from __future__ import annotations

import os
import sys
import time

from didww_verification import BasicAuth, Environment, VerificationClient


def main(verification_id: str) -> int:
    auth = BasicAuth(os.environ["DIDWW_KEY"], os.environ["DIDWW_SECRET"])
    deadline = time.monotonic() + 120  # a verification's own lifetime

    with VerificationClient(auth, environment=Environment.SANDBOX) as client:
        while time.monotonic() < deadline:
            verification = client.get_verification(verification_id)
            # Anything but "pending" is terminal. Listing the terminal ones instead
            # would poll a status added after this release forever.
            if verification.is_finished:
                print(f"{verification.status}: {verification.error_detail or 'ok'}")
                return 0 if verification.status == "verified" else 1
            time.sleep(2)

    print("gave up waiting")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
