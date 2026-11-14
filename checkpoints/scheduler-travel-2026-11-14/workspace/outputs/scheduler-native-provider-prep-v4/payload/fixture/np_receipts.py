"""Bounded sanitized evidence builders for native-provider prep.

PREPARED ONLY. Never emit secrets, raw bodies, plaintext tokens, cookies, or private keys.
Allowlisted typed evidence (token_rollback_ack, terminal classifications, hashes) is preserved.
Runtime executed/authorization flags must truthfully describe the actual authorized run —
preparation defaults are False; successful execution receipts must not inherit prep-only False.
"""
from __future__ import annotations

from typing import Any


RECEIPT_VERSION = "native-provider-prep-v4"

# Keys containing these fragments are dropped UNLESS explicitly allowlisted.
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

# Explicitly reviewed typed evidence — safe booleans/hashes/classifications.
_ALLOWLISTED_EVIDENCE_KEYS = frozenset(
    {
        "token_rollback_ack",
        "token_rollback_acked",
        "token_terminal",
        "token_terminal_class",
        "token_commit_ack",
        "oauth_request_count",
        "covering_token_terminal",
        "attempt_token_sha256_16",
        "label_hash",
        "alias_hash",
        "case_token_sha256_16",
    }
)


def _forbidden_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _ALLOWLISTED_EVIDENCE_KEYS or key in _ALLOWLISTED_EVIDENCE_KEYS:
        return False
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


def build_receipt(
    *,
    executed: bool = False,
    launch_authorized: bool = False,
    prep_is_not_pass: bool = True,
    endpoint: str = "unbound",
    **fields: Any,
) -> dict[str, Any]:
    """Build sanitized receipt. Callers must pass truthful executed/launch_authorized."""
    payload = {
        "receipt_version": RECEIPT_VERSION,
        "executed": bool(executed),
        "launch_authorized": bool(launch_authorized),
        "prep_is_not_pass": bool(prep_is_not_pass),
        "endpoint": endpoint,
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
    observations: dict[str, Any],
    t_plan_iso: str,
    t_check_iso: str,
    measured: dict[str, Any] | None = None,
    peer_exchange_inventory: list[dict[str, Any]] | None = None,
    resource_disposition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-case evidence including measured native oracles (not OBSERVED strings alone)."""
    return build_receipt(
        kind="case_result",
        case_id=case_id,
        passed=passed,
        skipped=False,
        workers_joined=workers_joined,
        expected_unknown=expected_unknown,
        observations=dict(observations),
        measured=dict(measured or {}),
        peer_exchange_inventory=list(peer_exchange_inventory or []),
        resource_disposition=dict(resource_disposition or {}),
        t_plan=t_plan_iso,
        t_check=t_check_iso,
    )


def suite_report_receipt(
    *,
    report: dict[str, Any],
    case_results: list[dict[str, Any]],
    implementation_status: dict[str, str],
    console_sha256: str,
    console_bytes: int,
    executed: bool,
    launch_authorized: bool | None = None,
) -> dict[str, Any]:
    """Flat top-level schema matching np_supervisor.ProviderDockerOps.run_attached readers.

    Fields runtime_pins/ca_sha256/host_docker_ownership/case_ids live at TOP LEVEL
    (not nested under report). case_results carry measured native oracles.
    Runtime executed=true is an observation; human launch_authorized is omitted
    unless an explicit host-ledger value is supplied (never invented by the runner).
    """
    flat = {
        "kind": "runner_suite_report",
        "case_ids": list(report.get("case_ids") or []),
        "passed": report.get("passed"),
        "failed": report.get("failed"),
        "skipped": report.get("skipped"),
        "joined_workers": report.get("joined_workers"),
        "unexpected_unknown": report.get("unexpected_unknown"),
        "expected_unknown_cases": list(report.get("expected_unknown_cases") or []),
        "runtime_pins": report.get("runtime_pins"),
        "ca_sha256": report.get("ca_sha256"),
        "docker_daemon_calls": report.get("docker_daemon_calls", 0),
        "host_docker_ownership": report.get("host_docker_ownership"),
        "case_results": list(case_results),
        "implementation_status": dict(implementation_status),
        "console_sha256": console_sha256,
        "console_bytes": console_bytes,
        "console_policy": "hash_only_raw_console_not_retained",
    }
    receipt = build_receipt(executed=executed, **flat)
    if launch_authorized is None:
        receipt.pop("launch_authorized", None)
    else:
        receipt["launch_authorized"] = bool(launch_authorized)
    return receipt


if __name__ == "__main__":
    raise SystemExit("HELD: np_receipts preparation only; no receipt emission")
