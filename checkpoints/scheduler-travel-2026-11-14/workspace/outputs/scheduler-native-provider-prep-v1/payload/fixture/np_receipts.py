"""Bounded sanitized evidence builders for native-provider prep.

PREPARED ONLY. Never emit secrets, raw bodies, tokens, cookies, or private keys.
"""
from __future__ import annotations

from typing import Any


RECEIPT_VERSION = "native-provider-prep-v1"

_FORBIDDEN_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "bearer",
    "signer",
    "cookie",
    "plaintext",
    "raw_request",
    "raw_body",
    "refresh_token",
    "access_token",
    "client_secret",
    "private_key",
    "fernet",
)


def _forbidden_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _FORBIDDEN_KEY_FRAGMENTS)


def redact_mapping(value: Any) -> Any:
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
    payload = {
        "receipt_version": RECEIPT_VERSION,
        "executed": False,
        "launch_authorized": False,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        **fields,
    }
    return redact_mapping(payload)


def sanitize_cleanup_failure(exc: BaseException) -> dict[str, str]:
    return {"kind": type(exc).__name__}


def observation_record(
    *,
    case_id: str,
    oracle_name: str,
    observed: str,
    planning_ids: tuple[str, ...] | list[str],
    t_plan_iso: str | None = None,
    t_check_iso: str | None = None,
) -> dict[str, Any]:
    return build_receipt(
        kind="case_observation",
        case_id=case_id,
        oracle_name=oracle_name,
        observed=observed,
        planning_ids=list(planning_ids),
        t_plan=t_plan_iso,
        t_check=t_check_iso,
    )


def case_result_receipt(
    *,
    case_id: str,
    passed: bool,
    workers_joined: bool,
    expected_unknown: bool,
    observations: dict[str, str],
    t_plan_iso: str,
    t_check_iso: str,
) -> dict[str, Any]:
    return build_receipt(
        kind="case_result",
        case_id=case_id,
        passed=passed,
        skipped=False,
        workers_joined=workers_joined,
        expected_unknown=expected_unknown,
        observations=dict(observations),
        t_plan=t_plan_iso,
        t_check=t_check_iso,
    )


if __name__ == "__main__":
    raise SystemExit("HELD: np_receipts preparation only; no receipt emission")
