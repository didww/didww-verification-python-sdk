"""Start a verification, then report the code the user entered.

DIDWW_KEY=... DIDWW_SECRET=... python examples/quickstart_sync.py +37112345678
"""

from __future__ import annotations

import os
import sys

from didww_verification import (
    BasicAuth,
    DidwwValidationError,
    Environment,
    SmsOptions,
    VerificationClient,
)


def main(destination: str) -> int:
    auth = BasicAuth(os.environ["DIDWW_KEY"], os.environ["DIDWW_SECRET"])

    with VerificationClient(auth, environment=Environment.SANDBOX) as client:
        verification = client.start_verification(
            destination=destination,
            delivery_method="sms",
            sms=SmsOptions(languages=["en-US"]),
        )
        print(f"started {verification.id}, expires at {verification.expires_at}")
        if verification.sms is not None:
            print(f"rendered in {verification.sms.language}")

        code = input("code from the SMS: ").strip()

        # One attempt is consumed whatever the outcome, so never loop on this.
        try:
            verification = client.report_verification(
                verification.id, delivery_method="sms", code=code
            )
        except DidwwValidationError as exc:
            if not exc.has_code("code_invalid"):
                raise
            print("wrong code; the verification is still pending")
            return 1

    if verification.status == "verified":
        print("verified")
        return 0
    print(f"{verification.status}: {verification.error_detail or verification.error_code}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
