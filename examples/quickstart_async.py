"""The asynchronous client: same surface, with await.

DIDWW_KEY=... DIDWW_SECRET=... python examples/quickstart_async.py +37112345678
"""

from __future__ import annotations

import asyncio
import os
import sys

from didww_verification import (
    AsyncVerificationClient,
    BasicAuth,
    DidwwValidationError,
    Environment,
)


async def main(destination: str) -> int:
    auth = BasicAuth(os.environ["DIDWW_KEY"], os.environ["DIDWW_SECRET"])

    async with AsyncVerificationClient(auth, environment=Environment.SANDBOX) as client:
        verification = await client.start_verification(
            destination=destination, delivery_method="sms"
        )
        print(f"started {verification.id}")

        code = await asyncio.to_thread(input, "code from the SMS: ")
        try:
            verification = await client.report_verification(
                verification.id, delivery_method="sms", code=code.strip()
            )
        except DidwwValidationError as exc:
            if not exc.has_code("code_invalid"):
                raise
            print("wrong code; the verification is still pending")
            return 1

    print(verification.status)
    return 0 if verification.status == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1])))
