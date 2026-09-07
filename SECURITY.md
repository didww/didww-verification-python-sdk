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
