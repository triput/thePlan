"""Finite native-provider case inventory and immediate STOP oracles.

PREPARED ONLY. Not executed under preparation approval.
Canonical inventory: Case-Registry jim-v2 BBFEF333… — 27 native STOP + 4 CF witnesses.
All 76 planning IDs mapped in data/Case-Requirement-Map.json; no silent omission.

Observation aids (Native-Deadline-TLS-Observation-Review.md SHA256
1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069 + Source-Pins;
T02-T08-Witness-Matching-20261112.md):
- Measure from actual ASGI budget admission; supervisor kill ≠ app deadline proof
- sent=True is uncertainty-before-call, not byte count
- Peer prefix-only receive ≠ sender partial completion proof
- Preserve ReleasePlan→Counter→CoveringHTTP→JoinedTLS
- ASGI disconnect ≠ provider EOF ≠ task cancellation
- Complete close-delimited positive and orderly short-CL negative need distinct observations
- Expected app UNKNOWN never absorbs unjoined/invalid fixture STOP
- Framing excess probes (8 bytes / 3 items vs 5) = reduced-limit logical evidence,
  not native 10k/16MiB overrun — cite matching witnesses; retain focused gap controls
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ATTEMPT_VALIDITY_SECONDS = 600
WORK_DEADLINE_SECONDS = 210
REQUEST_DEADLINE_SECONDS = 240
CLEANUP_ALLOWANCE_SECONDS = 30


@dataclass(frozen=True)
class Oracle:
    name: str
    planning_ids: tuple[str, ...]
    expected: str
    stop_on_mismatch: bool = True


@dataclass(frozen=True)
class CaseDecl:
    case_id: str
    planning_ids: tuple[str, ...]
    batch: str
    stimulus: str
    oracles: tuple[Oracle, ...]
    expected_unknown: bool = False
    native_tls_claim: bool = True
    notes: str = ""


def _o(name: str, *planning: str, expected: str = "OBSERVED") -> Oracle:
    return Oracle(name=name, planning_ids=tuple(planning), expected=expected)


# --- A. 27 native STOP units ---
NATIVE_CASES: tuple[CaseDecl, ...] = (
    CaseDecl(
        "NP-V-MS-NONEXPIRED",
        (),
        "B1",
        "Nonexpired MS seed; get_valid_access_token",
        (_o("no_oauth_request"), _o("token_rollback_ack"), _o("identity_event_assessment_separate")),
        native_tls_claim=False,
        notes="Vertical composition; not a T06 success",
    ),
    CaseDecl(
        "NP-V-MS-REFRESH",
        ("T06-SUCCESS-MICROSOFT",),
        "B1",
        "Explicitly expired MS token + synthetic MS client/secret/redirect/tenant",
        (_o("owning_ms_refresh_joinedtls", "T06-SUCCESS-MICROSOFT"), _o("token_commit"), _o("persistence")),
    ),
    CaseDecl(
        "NP-V-MS-TOKEN-THEN-IMPORT-FAIL",
        (),
        "B1",
        "After TOKEN COMMIT, force known event-import failure",
        (_o("refreshed_tokens_remain"), _o("parent_import_rollback_separate"), _o("assessment_separate")),
        notes="TOKEN versus IMPORT terminal separation",
    ),
    CaseDecl(
        "NP-V-MS-INVALID",
        ("T06-INVALID-GRANT-MICROSOFT",),
        "B1",
        "Synthetic MS invalid_grant on owning refresh",
        (_o("token_rejected_after_unchanged_unit_rollback", "T06-INVALID-GRANT-MICROSOFT"),),
    ),
    CaseDecl(
        "NP-V-GOOGLE-REFRESH",
        ("T06-SUCCESS-GOOGLE",),
        "B1",
        "Explicitly expired Google token + synthetic Google settings",
        (_o("owning_google_refresh", "T06-SUCCESS-GOOGLE"), _o("token_commit_not_ms_proof")),
    ),
    CaseDecl(
        "NP-V-GOOGLE-INVALID",
        ("T06-INVALID-GRANT-GOOGLE",),
        "B1",
        "Synthetic Google invalid_grant on owning refresh",
        (_o("token_rejected_path_not_ms", "T06-INVALID-GRANT-GOOGLE"),),
    ),
    CaseDecl(
        "NP-T06-BEFORE-SEND",
        ("T06-BEFORE-SEND",),
        "B1",
        "Pre-send refusal/stop stimulus",
        (_o("no_token_mutation_claim", "T06-BEFORE-SEND"),),
    ),
    CaseDecl(
        "NP-T06-MALFORMED-ACK",
        ("T06-MALFORMED-ACK",),
        "B1",
        "After-send malformed OAuth ack body",
        (_o("unknown_remap_no_known_failure_from_parser_alone", "T06-MALFORMED-ACK"),),
        expected_unknown=True,
    ),
    CaseDecl(
        "NP-T06-TRUNCATED-ACK",
        ("T06-TRUNCATED-ACK",),
        "B1",
        "After-send truncated OAuth ack",
        (_o("unknown_local_tokens_retained_as_observed", "T06-TRUNCATED-ACK"),),
        expected_unknown=True,
    ),
    CaseDecl(
        "NP-T06-OTHER",
        ("T06-OTHER-ERROR",),
        "B1",
        "Non-invalid_grant OAuth error body",
        (_o("unknown_branch_as_sourced", "T06-OTHER-ERROR"),),
        expected_unknown=True,
    ),
    CaseDecl(
        "NP-T06-PARTIAL",
        ("T06-PARTIAL-SEND",),
        "B1",
        "OAuth partial send mid-body",
        (_o("unknown_no_replay", "T06-PARTIAL-SEND"),),
        expected_unknown=True,
    ),
    CaseDecl(
        "NP-T06-LOST",
        ("T06-LOST-ACK",),
        "B1",
        "Lost ack after send",
        (_o("unknown_disposable_db_retained", "T06-LOST-ACK"),),
        expected_unknown=True,
    ),
    CaseDecl(
        "NP-T03-VALID",
        ("T03-VALID",),
        "B2",
        "verify-full CA+hostname via JoinedTLS to vendor SAN leaf",
        (_o("handshake_and_useful_app_data", "T03-VALID"),),
    ),
    CaseDecl(
        "NP-T03-WRONG-CA",
        ("T03-WRONG-CA",),
        "B2",
        "Distinct wrong trust material",
        (_o("refuse_before_useful_application_data", "T03-WRONG-CA"),),
    ),
    CaseDecl(
        "NP-T03-WRONG-NAME",
        ("T03-WRONG-NAME",),
        "B2",
        "Mismatched SAN",
        (_o("refuse", "T03-WRONG-NAME"),),
    ),
    CaseDecl(
        "NP-T03-HANDSHAKE-STALL",
        ("T03-HANDSHAKE-STALL",),
        "B3",
        "Peer stall pre-handshake; production 210/240 clocks",
        (_o("first_guard_deadline_real_elapsed", "T03-HANDSHAKE-STALL"),),
    ),
    CaseDecl(
        "NP-T03-TCP-REFUSAL",
        ("T03-TCP-REFUSAL",),
        "B2",
        "Numeric dial to closed port",
        (_o("typed_connect_failure_no_fake_empty_receive", "T03-TCP-REFUSAL"),),
    ),
    CaseDecl(
        "NP-T04-HEADER-STALL",
        ("T04-HEADER-STALL",),
        "B3",
        "Peer stall in header phase; production clocks",
        (_o("first_guard_header_phase_deadline", "T04-HEADER-STALL"),),
    ),
    CaseDecl(
        "NP-T04-BODY-STALL",
        ("T04-BODY-STALL",),
        "B3",
        "Peer stall in body phase; production clocks",
        (_o("first_guard_body_phase_deadline", "T04-BODY-STALL"),),
    ),
    CaseDecl(
        "NP-T04-PARTIAL-SEND",
        ("T04-PARTIAL-SEND",),
        "B4",
        "Partial request send observed",
        (_o("joined_retirement_no_retry", "T04-PARTIAL-SEND"),),
        expected_unknown=True,
    ),
    CaseDecl(
        "NP-T04-DEADLINE",
        ("T04-DEADLINE",),
        "B4",
        "Explicit app deadline classification",
        (_o("distinct_from_supervisor_kill", "T04-DEADLINE"),),
    ),
    CaseDecl(
        "NP-T04-DISCONNECT",
        ("T04-DISCONNECT",),
        "B4",
        "ASGI/request-disconnect + joined worker/provider retirement",
        (_o("unknown_sanitized_not_abrupt_provider_eof", "T04-DISCONNECT"),),
        expected_unknown=True,
        notes="Not abrupt provider EOF (see NP-T05-ABRUPT)",
    ),
    CaseDecl(
        "NP-T05-ORDERLY-CLOSE",
        ("T05-VALID-COMPLETE-CONTENT-LENGTH", "T05-SHORT-LENGTH-VALID-JSON"),
        "B5",
        "Orderly close_notify with close-delimited, exact fixed-length and short-CL completeness requal",
        (
            Oracle(
                name="orderly_close_delimited_complete_accepted",
                planning_ids=(),
                expected="ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY",
            ),
            Oracle(
                name="orderly_fixed_length_complete_accepted",
                planning_ids=("T05-VALID-COMPLETE-CONTENT-LENGTH",),
                expected="ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY",
            ),
            Oracle(
                name="orderly_short_cl_valid_json_prefix_refused",
                planning_ids=("T05-SHORT-LENGTH-VALID-JSON",),
                expected="REFUSED_AFTER_ORDERLY_CLOSE_NOTIFY",
            ),
        ),
        notes=(
            "Separate named observations required: (a) supplementary complete "
            "close-delimited accepted after orderly close_notify (no planning ID), "
            "(b) complete exact fixed-length (Content-Length equals body) accepted after "
            "orderly close_notify (T05-VALID-COMPLETE-CONTENT-LENGTH only) AND (c) valid-JSON "
            "prefix shorter than Content-Length refused after orderly close_notify. Abrupt TLS distinct."
        ),
    ),
    CaseDecl(
        "NP-T05-ABRUPT-TRUNCATION",
        (),
        "B5",
        "Abrupt TLS truncate without close_notify",
        (_o("classified_distinct_from_malformed_and_asgi_disconnect"),),
    ),
    CaseDecl(
        "NP-T07-OWNED-SOCKET",
        (
            "T07-RESPONSE-CLOSE-AFTER-SUCCESS",
            "T07-RESPONSE-CLOSE-AFTER-PRIMARY-FAILURE",
            "T07-TRANSPORT-CLOSE-AFTER-SUCCESS",
            "T07-TRANSPORT-CLOSE-AFTER-PRIMARY-FAILURE",
            "T07-BOTH-CLOSE-AFTER-SUCCESS",
            "T07-OPEN-CLOSE",
            "T07-SETBLOCKING",
        ),
        "B5",
        "Real owned peer/reader under JoinedTLS",
        (
            _o("t07_response_close_after_success", "T07-RESPONSE-CLOSE-AFTER-SUCCESS"),
            _o("t07_response_close_after_primary_failure", "T07-RESPONSE-CLOSE-AFTER-PRIMARY-FAILURE"),
            _o("t07_transport_close_after_success", "T07-TRANSPORT-CLOSE-AFTER-SUCCESS"),
            _o("t07_transport_close_after_primary_failure", "T07-TRANSPORT-CLOSE-AFTER-PRIMARY-FAILURE"),
            _o("t07_both_close_after_success", "T07-BOTH-CLOSE-AFTER-SUCCESS"),
            _o("t07_open_close", "T07-OPEN-CLOSE"),
            _o("t07_setblocking", "T07-SETBLOCKING"),
        ),
        notes="T07 real-resource observations named individually; no grouped-label waiver",
    ),
    CaseDecl(
        "NP-T07-BOTH-AFTER-FAILURE",
        ("T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE",),
        "B5",
        "Primary failure then both-close branch",
        (_o("combined_both_close_after_failure", "T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE"),),
        notes="Host-fake PRIMARY-BOTH-CLOSES does not close this native obligation",
    ),
    CaseDecl(
        "NP-T08-OWNERSHIP",
        ("T08-FOREIGN-THREAD", "T08-FOREIGN-CLOSE", "T08-REUSE"),
        "B5",
        "One owned peer lifecycle; four named oracles",
        (
            _o("foreign_check", "T08-FOREIGN-THREAD"),
            _o("foreign_close", "T08-FOREIGN-CLOSE"),
            _o("reuse_forbid", "T08-REUSE"),
            _o("owner_retirement"),
        ),
        notes="Each checked immediately; STOP on mismatch. T08-NESTED/RESET remain GAP/focused-fake.",
    ),
)

# --- B. 4 pure CF witnesses (refuse-before-send; no native TLS claim) ---
CF_WITNESS_CASES: tuple[CaseDecl, ...] = (
    CaseDecl(
        "NP-T01-USERINFO-CF",
        ("T01-ORIGIN-USERINFO",),
        "B0",
        "Origin userinfo refuse-before-send",
        (_o("refuse_before_send", "T01-ORIGIN-USERINFO"),),
        native_tls_claim=False,
    ),
    CaseDecl(
        "NP-T01-FRAGMENT-CF",
        ("T01-ORIGIN-FRAGMENT",),
        "B0",
        "Origin fragment refuse-before-send",
        (_o("refuse_before_send", "T01-ORIGIN-FRAGMENT"),),
        native_tls_claim=False,
    ),
    CaseDecl(
        "NP-T01-CONTROL-CHAR-CF",
        ("T01-ORIGIN-CONTROL-CHAR",),
        "B0",
        "Origin control-character refuse-before-send",
        (_o("refuse_before_send", "T01-ORIGIN-CONTROL-CHAR"),),
        native_tls_claim=False,
    ),
    CaseDecl(
        "NP-T01-PURPOSE-WRONG-CF",
        ("T01-PURPOSE-WRONG",),
        "B0",
        "Purpose-wrong refuse-before-send",
        (_o("refuse_before_send", "T01-PURPOSE-WRONG"),),
        native_tls_claim=False,
    ),
)

ALL_CASES: tuple[CaseDecl, ...] = NATIVE_CASES + CF_WITNESS_CASES


def case_ids(*, include_cf: bool = True) -> tuple[str, ...]:
    cases = ALL_CASES if include_cf else NATIVE_CASES
    return tuple(c.case_id for c in cases)


def expected_unknown_case_ids(*, include_cf: bool = True) -> tuple[str, ...]:
    cases = ALL_CASES if include_cf else NATIVE_CASES
    return tuple(c.case_id for c in cases if c.expected_unknown)


def registry_by_id(*, include_cf: bool = True) -> dict[str, CaseDecl]:
    cases = ALL_CASES if include_cf else NATIVE_CASES
    out = {c.case_id: c for c in cases}
    if len(out) != len(cases):
        raise RuntimeError("duplicate case_id in registry")
    return out


class SuiteStop(RuntimeError):
    """Immediate STOP on oracle mismatch. No retry / reseed."""


def check_oracles_immediate(case: CaseDecl, observations: dict[str, str]) -> None:
    """Enforce every named oracle immediately; STOP on mismatch."""
    for oracle in case.oracles:
        if oracle.name not in observations:
            raise SuiteStop(f"missing observation:{case.case_id}:{oracle.name}")
        if observations[oracle.name] != oracle.expected and oracle.stop_on_mismatch:
            raise SuiteStop(
                f"oracle mismatch:{case.case_id}:{oracle.name}:"
                f"expected={oracle.expected}:got={observations[oracle.name]}"
            )


def validate_inventory_counts() -> dict[str, int]:
    native = len(NATIVE_CASES)
    cf = len(CF_WITNESS_CASES)
    if native != 27:
        raise RuntimeError(f"native case count {native} != 27")
    if cf != 4:
        raise RuntimeError(f"cf witness count {cf} != 4")
    return {"native": native, "cf_witnesses": cf, "total_if_cf_included": native + cf}


# Explicit retained gaps (not waived)
RETAINED_GAPS: tuple[dict[str, str], ...] = (
    {
        "id": "T02-ITEMS-OVERFLOW",
        "disposition": "GAP",
        "note": (
            "Direct item overrun not established by N-1 + admission alone; "
            "host-fake EXCESS-ITEM-BYTE (RESULT 3905A070…; response_bytes=8 / items=3 vs 5) "
            "is reduced-limit logical evidence only — not native 10k/16MiB overrun. "
            "Cite T02-T08-Witness-Matching-20261112.md; retain focused gap controls."
        ),
    },
    {
        "id": "T02-BYTES-OVERFLOW",
        "disposition": "GAP",
        "note": (
            "Direct byte overrun retained; same host-fake reduced-limit witness scope "
            "as T02-ITEMS-OVERFLOW — not native TLS/full T02 closure."
        ),
    },
    {
        "id": "T08-NESTED",
        "disposition": "GAP_OR_FOCUSED_FAKE",
        "note": "ContextVar nesting; focused fake witness in check_native_provider (extracted covering_provider_context)",
    },
    {
        "id": "T08-RESET",
        "disposition": "GAP_OR_FOCUSED_FAKE",
        "note": "ContextVar reset normal/exceptional; focused fake witness in check_native_provider",
    },
    {
        "id": "T01-ORIGIN-FOREIGN-PORT",
        "disposition": "PORT_HOST_FAKE_PASS_NOT_NATIVE",
        "note": (
            "Port fake PASS 9/9 reconciled (RESULT B8C6353A… / Receipt 61F266A3… / "
            "Reconciliation E922DA61…). Verified finite host extracted-class HTTPSPeer "
            "origin-port admission only — still not native dial/TLS or full T01 closure. "
            "Assembly consumes policy 5F48FD7E… under verified PASS status."
        ),
    },
)

# Port dependency status (prep-v2 update)
PORT_DEPENDENCY_STATUS: dict[str, Any] = {
    "status": "VERIFIED_FINITE_HOST_PASS_9_OF_9",
    "result_sha256": "B8C6353A712382E16B601036034B32293EDEDF345388990D489B0E9AB9A12548",
    "receipt_sha256": "61F266A34BF7E4BD8BD5193D3DB6A315F02C9C9AC13D4AC51F80C73C62720961",
    "reconciliation_sha256": "E922DA6183B70D5DA9B1CBE19768F95E6B31578DA6B5594C2BD0CB5129861D7D",
    "policy_override_sha256": "5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88",
    "scope": "Host Python3.11 extracted-class HTTPSPeer origin-port admission only",
    "native_dial_tls": False,
    "full_t01_closure": False,
    "assembly_consumes_verified_pass": True,
}

OBSERVATION_AID_PINS: dict[str, str] = {
    "Native-Deadline-TLS-Observation-Review.md": (
        "1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069"
    ),
    "Source-Pins-Native-Observation-Review.json": "ALONGSIDE",
    "T02-T08-Witness-Matching-20261112.md": "PRESENT",
}

# First-increment implementation status (np_runner_entry.IMPLEMENTED_CASE_IDS)
# Incomplete cases remain HOLD in runner — never fabricated PASS.
CASE_IMPLEMENTATION_NOTES: dict[str, str] = {
    "NP-V-MS-NONEXPIRED": "IMPLEMENTED_SOURCE — first vertical; launch_ready gate still required",
    "NP-V-MS-REFRESH": (
        "IMPLEMENTED_SOURCE — separate single-case batch; expired MS seed, one OAuth "
        "exchange at production-derived tenant path, TOKEN COMMIT then ROLLBACK, five "
        "peer exchanges, semantic persisted-credential proof; launch_ready gate still "
        "required; no native PASS until an authorized run"
    ),
    "NP-T05-ORDERLY-CLOSE": (
        "IMPLEMENTED_SOURCE — production Counter/CoveringHTTP/default JoinedTLS; three separate "
        "sequential owned-peer observations after orderly close_notify: supplementary close-delimited "
        "complete accepted (exact body; scripted wire has no CL/TE), exact fixed-length complete "
        "accepted (exact body; scripted wire Content-Length equals body, no TE) and short-CL "
        "valid-JSON prefix refused (IncompleteRead); peer retired/joined before classification; "
        "no native PASS until an authorized run"
    ),
    "NP-T05-ABRUPT-TRUNCATION": (
        "IMPLEMENTED_SOURCE — abrupt TLS drop without close_notify mid-body; observed client class "
        "must be SSLEOFError or ConnectionResetError, distinct from framing/JSON refusal and ASGI "
        "disconnect; any other class STOPs; no native PASS until an authorized run"
    ),
}


if __name__ == "__main__":
    raise SystemExit("HELD: np_suite is preparation inventory only; no case execution")
