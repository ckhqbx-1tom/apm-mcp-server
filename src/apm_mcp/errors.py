from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SENSITIVE_KEYS = re.compile(
    r"(?i)(authorization|api[_-]?key|apikey|token|password|cookie|session)"
)


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Recursively redact known secret fields and configured secret values."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SENSITIVE_KEYS.search(str(key)) else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, secrets) for item in value)
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "[REDACTED]")
        return result
    return value


@dataclass(slots=True)
class APMError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, dict[str, str]]:
        return {"error": {"code": self.code, "message": self.message}}

