
import re


class SecretRedactor:
    """
    Removes known secrets from browser-observable text.
    """

    def __init__(
        self,
        secrets: list[str] | None = None,
    ):
        self.secrets = [
            secret
            for secret in (secrets or [])
            if secret
        ]

    def redact(
        self,
        text: str,
    ) -> str:

        redacted = text

        for secret in self.secrets:
            redacted = redacted.replace(
                secret,
                "[REDACTED]",
            )

        return redacted