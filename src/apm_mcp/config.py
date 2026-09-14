from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .errors import APMError


def _boolean(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise APMError("configuration_error", f"{name} must be true or false.")


def _positive_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise APMError("configuration_error", f"{name} must be a number.") from exc
    if parsed <= 0:
        raise APMError("configuration_error", f"{name} must be greater than zero.")
    return parsed


def _base_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise APMError("configuration_error", "APM_API_URL must be an absolute HTTP(S) URL.")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise APMError("configuration_error", "APM_API_URL must be a credential-free base URL.")
    if parts.path.rstrip("/"):
        raise APMError("configuration_error", "APM_API_URL must not include an Applications Manager endpoint path.")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


@dataclass(frozen=True, slots=True)
class Settings:
    api_url: str
    api_key: str
    verify_tls: bool = True
    ca_bundle: str | None = None
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    read_only: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        api_url = env.get("APM_API_URL", "").strip()
        api_key = env.get("APM_API_KEY", "")
        if not api_url:
            raise APMError("configuration_error", "APM_API_URL is required.")
        if not api_key:
            raise APMError("configuration_error", "APM_API_KEY is required.")
        ca_bundle = env.get("APM_CA_BUNDLE", "").strip() or None
        if ca_bundle:
            path = Path(ca_bundle)
            if not path.is_file() or not os.access(path, os.R_OK):
                raise APMError("configuration_error", "APM_CA_BUNDLE must be a readable file.")
        level = env.get("APM_LOG_LEVEL", "INFO").upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise APMError("configuration_error", "APM_LOG_LEVEL is invalid.")
        return cls(
            api_url=_base_url(api_url), api_key=api_key,
            verify_tls=_boolean("APM_VERIFY_TLS", env.get("APM_VERIFY_TLS", "true")),
            ca_bundle=ca_bundle,
            connect_timeout=_positive_float("APM_CONNECT_TIMEOUT", env.get("APM_CONNECT_TIMEOUT", "10")),
            read_timeout=_positive_float("APM_READ_TIMEOUT", env.get("APM_READ_TIMEOUT", "30")),
            read_only=_boolean("APM_MCP_READ_ONLY", env.get("APM_MCP_READ_ONLY", "true")),
            log_level=level,
        )
