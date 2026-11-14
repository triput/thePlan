"""I01/I02 receipt builders. Never emit secret-bearing fields."""
from __future__ import annotations

from typing import Any


RECEIPT_VERSION = "i01-i02-fixture-design-revise2"

_FORBIDDEN_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "bearer",
    "signer",
    "cookie_value",
    "plaintext",
    "raw_request",
    "refresh_token",
    "access_token",
)


def _forbidden_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _FORBIDDEN_KEY_FRAGMENTS)


def redact_mapping(value: Any) -> Any:
    """Recursively drop secret-bearing keys; preserve structure otherwise."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _forbidden_key(str(key)):
                continue
            out[str(key)] = redact_mapping(item)
        return out
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    if isinstance(value, tuple):
        return [redact_mapping(item) for item in value]
    return value


def build_receipt(**fields: Any) -> dict[str, Any]:
    payload = {"receipt_version": RECEIPT_VERSION, **fields}
    return redact_mapping(payload)


def sanitize_cleanup_failure(exc: BaseException) -> dict[str, str]:
    return {"kind": type(exc).__name__}
