"""Poll a verification to its conclusion.

Shows the two rules that matter: stop on `is_finished` rather than on a list of
statuses you know today, and treat a bad outcome as data rather than an exception.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

from didww_verification import BasicAuth, Environment, VerificationClient


def main(verification_id: str) -> int:
    auth = BasicAuth(os.environ["DIDWW_KEY"], os.environ["DIDWW_SECRET"])

    with VerificationClient(auth, environment=Environment.SANDBOX) as client:
        verification = client.get_verification(verification_id)
        # The application's own configured code lifetime (60-600s, default 300),
        # not a fixed window -- read it from the verification rather than hard-coding it.
        deadline = verification.expires_at or datetime.now(timezone.utc)

        while True:
            # Anything but "pending" is terminal. Listing the terminal ones instead
            # would poll a status added after this release forever.
            if verification.is_finished:
                print(f"{verification.status}: {verification.error_detail or 'ok'}")
                return 0 if verification.status == "verified" else 1
            if datetime.now(timezone.utc) >= deadline:
                break
            time.sleep(2)
            verification = client.get_verification(verification_id)

    print("gave up waiting")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
