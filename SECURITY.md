# Security

To report a vulnerability in this SDK, email <support@didww.com> rather than opening a
public issue.

Please include the SDK version, a minimal reproduction, and the impact you believe it has.

## Handling secrets

Application secrets are excluded from the `repr` of every object in this SDK, so they do not
appear in a traceback or a logged object. They can still reach a log through your own code --
do not log the objects you construct them from.

`Verification.raw` is off by default. When enabled it retains the decoded payload, including
the destination number, for as long as the object lives.

## Phone numbers in logs

This SDK does not log. Its HTTP client, httpx2, logs every request's method and URL at `INFO`
on the `httpx2` logger, and a `by_number` URL contains the destination number. If your
application logs at `INFO`, raise that logger to `WARNING`.
