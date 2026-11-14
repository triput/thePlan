#!/usr/bin/env python3
"""HELD fake-only checker for the MS-refresh merge preparation.

Matt, 2026-11-13. AUTHORING ONLY. This file has not been imported, parsed, compiled
or run. Each later run needs Trish's explicit one-shot approval of the exact reviewed
command and hashes.

The file name is kept as check_native_provider.py so the byte-identical, previously
reviewed launcher (launch_check.py, D22C37E3...) and outer admission
(verify_admission.py, 7DCA32E2...) can be reused unchanged.

Scope: merge/lineage/selection/batch-separation proof over raw-pinned bytes, plus an
explicit applicability map that ties the merged bytes to the units already proved by
the worker-observer fake (341074AE), the peer-close fake (17EA148E) and the MS-refresh
fake v2 (CC4D49E7 and roles 5/6/8/10). Text identity of each extracted unit is the
link; changed units are named and not credited with earlier PASS labels.

Standard library only (ast, hashlib, json, os, re, sys). Subject source is parsed to
locate segments and is never compiled or executed. No app or vendor imports, sockets,
TLS, PKI, database, Docker or child processes. The only write is the exclusive result.

Not proved: any native behavior; the merged NONEXPIRED or REFRESH case at runtime;
anything beyond the earlier fakes' own finite scopes.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
SUBJECTS = PACKET / "subjects"
EXPECTED = HERE / "EXPECTED-FAKE-STRUCTURAL.json"
RESULT = HERE / "FAKE-NATIVE-PROVIDER-RESULT.json"
MAX_RESULT = 262144
PACKET_NAME = "scheduler-ms-merge-fake-prep-matt-v1"

SUBJECT_PINS = {
    "runner/base.py": "40A1BA8E9C3E320DD7DF9E06102CC29C0E1AFAAD4213EC0FECF9FE34455BF73F",
    "runner/ms.py": "CC4D49E758F22E5E34C0D6093946CA390BC95A4C320C3D92B24AD723FA8634FF",
    "runner/observer.py": "341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645",
    "runner/merged.py": "F7CFD3E6BA0107B3482766C3A8FA505C5BADD287DF843FACAEA2E79CFFE5385C",
    "diff/observer.diff": "2023F97B5695BF690F50186C56B4DD3FCFF1A2BAFB3CA637B1051F400F3F2468",
    "diff/msrefresh.diff": "A805B9B0332B3619D33DBB712BD695BDF67AD3A41B2A925A0C8759745B8D6DD8",
    "manifest/base.txt": "3B25ABB656F991B3B80F012C9E67E5840E48AAACD3AE2336DE13AFB8039B2A90",
    "manifest/ms.txt": "BD48E400924E8D6DD17597F7845E20FC01F1889AFEEAD743880CB3BF2623472D",
    "manifest/peerclose.txt": "74B637D46586E1C8FD94EBEE8E3BB29581131C592B881D695D88BA1D509CCE45",
    "manifest/nonexpired.txt": "14FA30AD16E719150CA81F07274FF6AC8D3A2D80A065296D9FDB2830E2B00B46",
    "manifest/refresh.txt": "845182697A8BFA0142A15E4AC2261F33AD797D30440A110A308E3BC2FB4C2348",
    "config/nonexpired-runner-config.json": "9411AC387CCB735751E3D22C580EEFB2F9ADEE92F2E3725E1E36B7EACE7BE929",
    "config/refresh-runner-config.json": "108D8D1E5FEE4F1DBAB3FC6023AD018D7A5442C79C5012BD4D43A4DBAC6EE11A",
    "config/nonexpired-launch-config.json": "263CF5DDB8E2127C3F830DFABCB6EAE7F0D3FBF43CC87CF40ACF077C13249270",
    "config/refresh-launch-config.json": "197F4C7DE61A9B50930D97A374468330B7E243407A2BF35528A02AA66C8FE713",
}

CONTROL_IDS = (
    "SUBJECT-PINS",
    "MERGE-REDERIVATION",
    "OBSERVER-PRESERVED",
    "REFRESH-PRESERVED",
    "TOP-LEVEL-PARTITION",
    "ROLE-SELECTION",
    "BATCH-SEPARATION",
    "PRIOR-FAKE-APPLICABILITY",
    "ACTUAL-SOURCE-MUTANTS",
)

RUNNER = "fixture/np_runner_entry.py"
PEER = "fixture/np_provider_peer.py"
RUNNER_CONFIG = "runner-config.json"
MS_ROLES = ("fixture/np_suite.py", "fixture/np_receipts.py", "fixture/np_provider_transcript.py",
            "fixture/np_auth_seed.py")
MERGED_RUNNER_PIN = SUBJECT_PINS["runner/merged.py"]
PEER_FIXED = "17EA148E6DE9E30485992FC49C310975076F5F4A71AB3AA9441B3B63C1ADA039"
PEER_OLD = "5568AF73DD42FEB5B8E2FE4D723AD4FB0339CBF4B889F5472995ABC628F72A55"
ROOT_N = "scheduler-native-provider-ms-merge-nonexpired-prep-matt-v1"
ROOT_F = "scheduler-native-provider-ms-merge-refresh-prep-matt-v1"
FOREIGN_ROOTS = ("scheduler-native-provider-peer-close-prep-matt-v1", "scheduler-ms-refresh-prep-matt-v1",
                 "scheduler-native-provider-diagnostic-launch-dex-v1", "peer-close-launch-dex-v1")
# MS-refresh fake v2 candidate subject pins (from its reviewed packet manifest).
MS_FAKE_V2_PINS = {
    "fixture/np_suite.py": "46C9443D13E4CA526DEE4BEF5747D65AA0549CA0FFA963A8F8EB44595485370D",
    "fixture/np_receipts.py": "7F27A3C2CBCA73C27DCEC6C9DCF6277C7F131ACC3A561C4170636EAB5D5E24C7",
    "fixture/np_provider_transcript.py": "0AA3BC093711B7EEBADD1F23A80BF86F2B5AEAB4C1224014537BB051FDDCE52E",
    "fixture/np_auth_seed.py": "2ADFA3ADCFDA8DB4D9D32EDFC9950AF354CE29ADFA1B5A8162FD5182DC22ED05",
}

OBSERVER_UNITS = ("_install_worker_exception_observer", "_run_np_v_ms_nonexpired", "stop_payload")
# Every top-level unit the MS-refresh diff A805B9B0 added or changed (statically listed).
REFRESH_NEW_UNITS = ("_ms_refresh_provider_routes", "_require_production_ms_token_path",
                     "_actual_token_terminals", "_run_np_v_ms_refresh")
REFRESH_UNITS = REFRESH_NEW_UNITS + ("_make_implemented_case",)
ANCHOR_INSTALL = "            restore_worker_observer = _install_worker_exception_observer(worker_exceptions)\n"
ANCHOR_MAPPER = '    if case_id == "NP-V-MS-REFRESH":\n'
ANCHOR_IMPLEMENTED = 'frozenset({"NP-V-MS-NONEXPIRED", "NP-V-MS-REFRESH"})'


class WitnessFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WitnessFailure(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


_SUBJECT_TEXT: dict[str, str] = {}


def subject_text(rel: str) -> str:
    if rel not in _SUBJECT_TEXT:
        raise WitnessFailure(f"subject not admitted:{rel}")
    return _SUBJECT_TEXT[rel]


def check_subject_pins() -> dict[str, Any]:
    observed = {}
    for rel, pin in SUBJECT_PINS.items():
        data = (SUBJECTS / rel).read_bytes()
        digest = sha256_bytes(data)
        require(digest == pin, f"subject pin mismatch:{rel}")
        require(b"\r" not in data.replace(b"\r\n", b""), f"subject contains bare CR:{rel}")
        _SUBJECT_TEXT[rel] = data.decode("utf-8")
        observed[rel] = digest
    return {"subjects": observed, "control_kind": "raw_pin", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Patch-semantics re-derivation (pure text; zero fuzz; nearest unambiguous placement)
# ---------------------------------------------------------------------------

_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*")


def parse_hunks(diff: str) -> tuple[list[str], list[tuple[int, list[str], list[str]]]]:
    lines = diff.split("\n")
    files: list[str] = []
    hunks: list[tuple[int, list[str], list[str]]] = []
    i = 0
    while i < len(lines) and not lines[i].startswith("@@"):
        if lines[i].startswith("--- ") or lines[i].startswith("+++ "):
            files.append(lines[i][4:])
        elif lines[i] != "":
            raise WitnessFailure("unexpected diff header line")
        i += 1
    while i < len(lines):
        if lines[i] == "" and i == len(lines) - 1:
            break
        match = _HUNK.fullmatch(lines[i])
        require(match is not None, "malformed hunk header")
        old_start = int(match.group(1))
        old_len, new_len = int(match.group(2) or "1"), int(match.group(4) or "1")
        old: list[str] = []
        new: list[str] = []
        i += 1
        while i < len(lines) and not lines[i].startswith("@@"):
            if lines[i] == "" and i == len(lines) - 1:
                break
            tag, body = lines[i][:1], lines[i][1:]
            if tag == " ":
                old.append(body)
                new.append(body)
            elif tag == "-":
                old.append(body)
            elif tag == "+":
                new.append(body)
            else:
                raise WitnessFailure("unexpected hunk line")
            i += 1
        require((len(old), len(new)) == (old_len, new_len), "hunk length mismatch")
        hunks.append((old_start, old, new))
    return files, hunks


def apply_relocating(source: str, diff: str) -> tuple[str, int, list[int]]:
    """Apply hunks in order; each lands at the matching block nearest its expected line.

    Zero fuzz: the full old block (context + removals) must match exactly. A tie in
    distance refuses. The caller compares the result with a pinned expectation, so a
    wrong placement cannot yield a false PASS.
    """
    files, hunks = parse_hunks(diff)
    require(files == ["a/payload/fixture/np_runner_entry.py", "b/payload/fixture/np_runner_entry.py"],
            "diff touches unexpected files")
    src = source.split("\n")
    out: list[str] = []
    pos = 0
    offset = 0
    offsets: list[int] = []
    for old_start, old, new in hunks:
        expected = old_start - 1 + offset
        candidates = [i for i in range(pos, len(src) - len(old) + 1) if src[i:i + len(old)] == old]
        require(candidates, f"hunk at {old_start} has no exact match")
        best = min(abs(i - expected) for i in candidates)
        nearest = [i for i in candidates if abs(i - expected) == best]
        require(len(nearest) == 1, f"hunk at {old_start} ambiguous placement")
        at = nearest[0]
        out.extend(src[pos:at])
        out.extend(new)
        pos = at + len(old)
        offset = at - (old_start - 1)
        offsets.append(offset)
    out.extend(src[pos:])
    return "\n".join(out), len(hunks), offsets


def check_merge_rederivation() -> dict[str, Any]:
    base, ms, obs, merged = (subject_text(f"runner/{n}.py") for n in ("base", "ms", "observer", "merged"))
    obs_diff, ms_diff = subject_text("diff/observer.diff"), subject_text("diff/msrefresh.diff")
    cases = {}
    detail = {}
    for case, (src, diff, want, hunks_expected) in {
        "obs_from_base": (base, obs_diff, obs, 5),
        "ms_from_base": (base, ms_diff, ms, 3),
        "obs_onto_ms": (ms, obs_diff, merged, 5),
        "ms_onto_obs": (obs, ms_diff, merged, 3),
    }.items():
        derived, hunks, offsets = apply_relocating(src, diff)
        require(hunks == hunks_expected and derived == want, f"merge rederivation:{case}")
        cases[case] = "PASS"
        detail[case] = offsets
    return {"cases": cases, "placement_offsets": detail, "control_kind": "literal_text_patch_semantics",
            "observed": "PASS"}


# ---------------------------------------------------------------------------
# Unit extraction (AST locates segments only; nothing is compiled)
# ---------------------------------------------------------------------------

def _single(nodes: list[Any], what: str) -> Any:
    require(len(nodes) == 1, f"expected exactly one {what}, found {len(nodes)}")
    return nodes[0]


def node_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def unit_text(text: str, name: str) -> str:
    node = _single([n for n in ast.parse(text).body if node_name(n) == name], f"unit {name}")
    segment = ast.get_source_segment(text, node, padded=True)
    require(segment is not None, f"no segment:{name}")
    return segment


def main_guard_dump(text: str) -> str:
    guards = [n for n in ast.parse(text).body if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
              and isinstance(n.test.left, ast.Name) and n.test.left.id == "__name__"]
    return ast.dump(_single(guards, "__main__ guard"))


def oracle_observer(merged: str, observer: str) -> dict[str, str]:
    cases = {}
    for name in OBSERVER_UNITS:
        require(unit_text(merged, name) == unit_text(observer, name), f"observer preserved:{name}")
        cases[name] = "PASS"
    require(main_guard_dump(merged) == main_guard_dump(observer), "observer preserved:__main__")
    cases["main_guard"] = "PASS"
    return cases


def oracle_refresh(merged: str, ms: str) -> dict[str, str]:
    cases = {}
    for name in REFRESH_UNITS:
        require(unit_text(merged, name) == unit_text(ms, name), f"refresh preserved:{name}")
        cases[name] = "PASS"
    require(unit_text(merged, "IMPLEMENTED_CASE_IDS") == unit_text(ms, "IMPLEMENTED_CASE_IDS"),
            "refresh preserved:implemented")
    cases["IMPLEMENTED_CASE_IDS"] = "PASS"
    return cases


def check_observer_preserved() -> dict[str, Any]:
    cases = oracle_observer(subject_text("runner/merged.py"), subject_text("runner/observer.py"))
    return {"cases": cases, "control_kind": "extracted_text_identity", "observed": "PASS"}


def check_refresh_preserved() -> dict[str, Any]:
    cases = oracle_refresh(subject_text("runner/merged.py"), subject_text("runner/ms.py"))
    return {"cases": cases, "control_kind": "extracted_text_identity", "observed": "PASS"}


def differing_names(left: str, right: str) -> tuple[set[str], set[str]]:
    """Names of top-level nodes present (by exact dump) on one side only."""
    def table(text: str) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for node in ast.parse(text).body:
            result.setdefault(ast.dump(node), []).append(node_name(node) or "<unnamed>")
        return result
    lt, rt = table(left), table(right)
    only_left = {name for dump, names in lt.items() if dump not in rt for name in names}
    only_right = {name for dump, names in rt.items() if dump not in lt for name in names}
    for dump in set(lt) & set(rt):
        require(len(lt[dump]) == len(rt[dump]), "duplicate top-level node multiplicity changed")
    return only_left, only_right


def check_top_level_partition() -> dict[str, Any]:
    merged, obs, ms = (subject_text(f"runner/{n}.py") for n in ("merged", "observer", "ms"))
    cases = {}
    only_merged, only_obs = differing_names(merged, obs)
    require(only_merged == set(REFRESH_NEW_UNITS) | {"_make_implemented_case", "IMPLEMENTED_CASE_IDS"}
            and only_obs == {"_make_implemented_case", "IMPLEMENTED_CASE_IDS"}, "partition vs observer")
    cases["vs_observer"] = "PASS"
    only_merged, only_ms = differing_names(merged, ms)
    require(only_merged == {"_run_np_v_ms_nonexpired", "_install_worker_exception_observer"}
            and only_ms == {"_run_np_v_ms_nonexpired"}, "partition vs ms")
    cases["vs_ms"] = "PASS"
    return {"cases": cases, "control_kind": "structural_source", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Manifest-level role selection and batch separation
# ---------------------------------------------------------------------------

def rows(text: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in text.splitlines():
        pin, sep, rel = line.partition("  ")
        require(sep == "  " and re.fullmatch(r"[0-9A-F]{64}", pin) is not None, "malformed manifest row")
        require(rel not in table, "duplicate manifest row")
        table[rel] = pin
    return table


def oracle_roles(n_text: str, f_text: str) -> dict[str, str]:
    base, ms, pc = (rows(subject_text(f"manifest/{n}.txt")) for n in ("base", "ms", "peerclose"))
    cases = {}
    for label, merged_text, config_side in (("n_rows", n_text, pc), ("f_rows", f_text, ms)):
        merged = rows(merged_text)
        require(set(merged) == set(base) == set(ms) == set(pc), f"role selection:{label}:path set")
        for rel, pin in merged.items():
            if rel == RUNNER:
                want = MERGED_RUNNER_PIN
            elif rel in MS_ROLES:
                require(ms[rel] != base[rel] and pc[rel] == base[rel], f"role selection:{label}:ms-only {rel}")
                want = ms[rel]
            elif rel == PEER:
                require(pc[rel] != base[rel] and ms[rel] == base[rel], f"role selection:{label}:pc-only peer")
                want = pc[rel]
            elif rel == RUNNER_CONFIG:
                want = config_side[rel]
            else:
                require(base[rel] == ms[rel] == pc[rel], f"role selection:{label}:shared {rel}")
                want = base[rel]
            require(pin == want, f"role selection:{label}:{rel}")
        cases[label] = "PASS"
    n_rows = rows(n_text)
    require(n_rows[PEER] == PEER_FIXED and rows(f_text)[PEER] == PEER_FIXED and base[PEER] == PEER_OLD,
            "role selection:peer")
    cases["peer_is_corrected"] = "PASS"
    api = [rel for rel in base if rel.startswith("api/")]
    require(len(api) == 234 and all(base[r] == ms[r] == pc[r] == n_rows[r] == rows(f_text)[r] for r in api),
            "role selection:api")
    cases["api_rows_unchanged"] = "PASS"
    return cases


def check_role_selection() -> dict[str, Any]:
    cases = oracle_roles(subject_text("manifest/nonexpired.txt"), subject_text("manifest/refresh.txt"))
    return {"cases": cases, "control_kind": "manifest_lineage", "observed": "PASS"}


def check_batch_separation() -> dict[str, Any]:
    cases = {}
    for label, case_id in (("nonexpired", "NP-V-MS-NONEXPIRED"), ("refresh", "NP-V-MS-REFRESH")):
        cfg = json.loads(subject_text(f"config/{label}-runner-config.json"))
        require(cfg.get("case_ids") == [case_id] and cfg.get("expected_unknown_cases") == []
                and cfg.get("launch_ready") is False, f"batch:{label} runner-config")
        cases[f"{label}_runner_config"] = "PASS"
    for label, case_id, own, other, manifest in (
            ("nonexpired", "NP-V-MS-NONEXPIRED", ROOT_N, ROOT_F, "manifest/nonexpired.txt"),
            ("refresh", "NP-V-MS-REFRESH", ROOT_F, ROOT_N, "manifest/refresh.txt")):
        raw = subject_text(f"config/{label}-launch-config.json")
        cfg = json.loads(raw)
        require(cfg.get("case_ids") == [case_id] and cfg.get("expected_unknown_cases") == []
                and cfg.get("launch_ready") is False and cfg.get("candidate_launch_ready_staged") is False
                and cfg.get("human_launch_authorized") is False and cfg.get("endpoint") == "unbound",
                f"batch:{label} launch-config gates")
        require(cfg.get("manifest_sha256") == SUBJECT_PINS[manifest], f"batch:{label} manifest pin")
        for key in ("docker_ops_config_path", "receipt_directory"):
            require(own in str(cfg.get(key)), f"batch:{label} {key} root")
        require(other not in raw and not any(root in raw for root in FOREIGN_ROOTS), f"batch:{label} foreign root")
        cases[f"{label}_launch_config"] = "PASS"
    n_rows, f_rows = rows(subject_text("manifest/nonexpired.txt")), rows(subject_text("manifest/refresh.txt"))
    require([rel for rel in n_rows if n_rows[rel] != f_rows[rel]] == [RUNNER_CONFIG], "batch:manifest difference")
    cases["sums_differ_only_runner_config"] = "PASS"
    return {"cases": cases, "control_kind": "config_data", "observed": "PASS"}


def check_prior_fake_applicability() -> dict[str, Any]:
    cases = {}
    n_rows = rows(subject_text("manifest/nonexpired.txt"))
    require(n_rows[PEER] == PEER_FIXED, "applicability:peer-close fake subject")
    cases["peer_close_fake_subject"] = "PASS"
    require(SUBJECT_PINS["runner/observer.py"] == "341074AEF88A9E438C0F488E6231572103E694FB5EB81D6F3AC6BD30517CD645",
            "applicability:worker fake subject")
    cases["worker_fake_subject"] = "PASS"
    require(SUBJECT_PINS["runner/ms.py"] == "CC4D49E758F22E5E34C0D6093946CA390BC95A4C320C3D92B24AD723FA8634FF"
            and all(n_rows[rel] == pin for rel, pin in MS_FAKE_V2_PINS.items()), "applicability:ms fake subjects")
    merged, base, obs = (subject_text(f"runner/{n}.py") for n in ("merged", "base", "observer"))
    # MS fake v2 credited NONEXPIRED as unchanged from 40A1BA8E; that label does NOT transfer.
    require(unit_text(merged, "_run_np_v_ms_nonexpired") != unit_text(base, "_run_np_v_ms_nonexpired")
            and unit_text(merged, "_run_np_v_ms_nonexpired") == unit_text(obs, "_run_np_v_ms_nonexpired"),
            "applicability:nonexpired label")
    cases["ms_fake_subjects_with_nonexpired_excluded"] = "PASS"
    return {"cases": cases, "not_transferred": ["ms-refresh-fake-v2 NONEXPIRED-AND-DIAGNOSTIC-PRESERVED:"
                                                 "np_runner_entry.py:_run_np_v_ms_nonexpired"],
            "control_kind": "applicability_map", "observed": "PASS"}


def _expect_detected(name: str, action: Callable[[], Any], prefix: str) -> str:
    try:
        action()
    except WitnessFailure as exc:
        if not str(exc).startswith(prefix):
            raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
        return "DETECTED"
    except BaseException:  # noqa: BLE001
        raise WitnessFailure(f"mutant {name} failed for an unrelated reason") from None
    raise WitnessFailure(f"mutant survived:{name}")


def mutate(text: str, old: str, new: str) -> str:
    require(text.count(old) == 1, f"mutation anchor not unique:{old!r}")
    return text.replace(old, new)


def check_actual_source_mutants() -> dict[str, Any]:
    merged, obs, ms = (subject_text(f"runner/{n}.py") for n in ("merged", "observer", "ms"))
    n_text, f_text = subject_text("manifest/nonexpired.txt"), subject_text("manifest/refresh.txt")
    peer_row_fixed = f"{PEER_FIXED}  {PEER}"
    mutants = {
        "observer_install_removed": (lambda: oracle_observer(mutate(merged, ANCHOR_INSTALL, ""), obs),
                                     "observer preserved:_run_np_v_ms_nonexpired"),
        "refresh_mapper_branch_disabled": (lambda: oracle_refresh(
            mutate(merged, ANCHOR_MAPPER, '    if case_id == "NP-V-MS-REFRESH-DISABLED":\n'), ms),
            "refresh preserved:_make_implemented_case"),
        "implemented_ids_reverted": (lambda: oracle_refresh(
            mutate(merged, ANCHOR_IMPLEMENTED, 'frozenset({"NP-V-MS-NONEXPIRED"})'), ms),
            "refresh preserved:implemented"),
        "peer_row_reverted": (lambda: oracle_roles(mutate(n_text, peer_row_fixed, f"{PEER_OLD}  {PEER}"), f_text),
                              "role selection:n_rows:fixture/np_provider_peer.py"),
    }
    results = {name: _expect_detected(name, action, prefix) for name, (action, prefix) in mutants.items()}
    return {"mutants": results, "control_kind": "actual_source_mutant", "observed": "PASS"}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

def exclusive_write_result(payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > MAX_RESULT:
        raise WitnessFailure("result exceeds byte cap")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(str(RESULT), flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
    finally:
        os.close(fd)


def compare_inventory(expected: dict[str, list[str]], actual: dict[str, list[str]]) -> None:
    require(list(expected) == list(actual), "inventory control keys differ")
    for key, cases in expected.items():
        require(list(actual[key]) == list(cases), f"inventory cases differ:{key}")


def run_checks() -> dict[str, Any]:
    if RESULT.exists():
        raise WitnessFailure("existing result; no replay")
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    require(expected.get("kind") == "ms-merge-fake-structural-expected", "EXPECTED kind")
    require(tuple(expected.get("control_ids_in_order") or ()) == CONTROL_IDS, "EXPECTED control inventory")
    functions = {
        "SUBJECT-PINS": check_subject_pins,
        "MERGE-REDERIVATION": check_merge_rederivation,
        "OBSERVER-PRESERVED": check_observer_preserved,
        "REFRESH-PRESERVED": check_refresh_preserved,
        "TOP-LEVEL-PARTITION": check_top_level_partition,
        "ROLE-SELECTION": check_role_selection,
        "BATCH-SEPARATION": check_batch_separation,
        "PRIOR-FAKE-APPLICABILITY": check_prior_fake_applicability,
        "ACTUAL-SOURCE-MUTANTS": check_actual_source_mutants,
    }
    require(tuple(functions) == CONTROL_IDS, "internal control order")
    controls = {}
    for control_id, function in functions.items():
        try:
            controls[control_id] = function()
        except WitnessFailure:
            raise
        except Exception as exc:
            raise WitnessFailure(f"{control_id}:{type(exc).__name__}") from None
    actual_nested = {k: list(v.get("cases") or v.get("mutants") or {})
                     for k, v in controls.items() if v.get("cases") or v.get("mutants")}
    compare_inventory(expected.get("nested_case_ids") or {}, actual_nested)
    failed = [k for k, v in controls.items() if v.get("observed") != "PASS"]
    nested = sum(len(v.get("cases") or v.get("mutants") or {"_": 1}) for v in controls.values())
    require(nested == expected.get("expected_nested_predicates"), "nested predicate total")
    return {
        "kind": "fake-native-provider-structural-result",
        "packet": PACKET_NAME,
        "executed": True,
        "launch_authorized": False,
        "prep_is_not_pass": True,
        "endpoint": "unbound",
        "native_proof": False,
        "controls": controls,
        "control_ids_in_order": list(controls.keys()),
        "passed": len(controls) - len(failed),
        "failed": len(failed),
        "failed_controls": failed,
        "nested_predicates": nested,
    }


def main() -> int:
    try:
        payload = run_checks()
    except WitnessFailure as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 125
    exclusive_write_result(payload)
    if payload["failed"] != 0:
        print(f"STOP: controls failed:{payload['failed_controls']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
