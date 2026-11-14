# Jim Host Launch Static Review v2 — scheduler-t07-fake-v1

**Reviewer:** Justin (for Jim)
**Date:** 2026-11-11
**Host dir:** `C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-t07-fake-v1/`
**Method:** Read-only static host launch review. Reconciles Dex prelaunch findings against staged v6 host packet. No packet/admission/commands/wrapper edits. No imports/compile/tests. No wrapper launch. No execution. No serialization probe.
**Flags:** `review_only=true`; `executed=false`; `launch_authorized=false`
**Supersedes:** v1 tip on-disk `7B3F7104A489EB5FB8C97B5BB0D3B48E9D13EF935035982128753B25A87F01BB` (**QUALIFIED ACCEPT** withdrawn)

## Disposition

**BLOCKERS** — Dex prelaunch withdrew the provisional v6 ACCEPT. Host surfaces remain pin-consistent and untouched, but the staged checker cannot be launch-authorized. Fresh checker successor (v7) is required before any renewed static host review / execution card.

Blocking findings: **5** (B1, B2, and three batch items).

## Dex findings reconciled (source of truth)

Read host notes:

- `V6-Prelaunch-Serialization-and-R01-Findings.md`
- `V6-Batch-Oracle-Evidence-Review.md`
- `Jim-v6-Prelaunch-Findings.txt` / `Jim-v6-Batch-Oracle-Feedback.txt`
- `Launch-Hold.json` (superseding prelaunch hold)

### B1 — Non-JSON `prior_completed` evidence (BLOCKER)

`drive_bounded_domain_no_later` returns `prior_completed` as live `types.SimpleNamespace` result objects. Caller controls record that evidence unchanged; `compare_to_expected` retains it; `main` calls `json.dumps(payload)` with no projection/default encoder. Success-path result emission would fail even if all controls pass.

**Required:** explicit primitive-field evidence projection; retain originals for behavior assertions; assert SUB-1 expected prior success. No `default=str` / repr / arbitrary dump / dropping evidence.

### B2 — C-R01 normal-close oracle disabled (BLOCKER)

Staged check contains `if probe.method_close_calls != 1 and probe.constructs == 0 and False: pass`. Condition never enforces; body cannot fail. Control records PASS without asserting both closes.

**Required:** instrument fake response close; assert exactly one response-close + one transport-close + valid returned result. Keep 41 control meanings; preserve unexpected-outcome refusal.

### Batch (fold before freeze) — BLOCKERS

1. **C-R12:** only checks `CoveringTransportRefused` with `sock=None`; does not assert closed/owner/socket identity unchanged or zero raw close. Requires instrumented fake socket + explicit fake-thread scope.
2. **C-PROV-BOUNDARY-ACCEPT:** records constants without calling `assert_provenance_boundary` on a valid UNKNOWN/provenance tuple. Negatives already exercise the validator; positive must too.
3. **C-R10/R11:** hardcode/assume `later_admission=False`; R10 stimulus is complete HTTP 500 `server_error` JSON (not malformed/lost). Descriptions must be truthful; distinct malformed/lost obligations remain open; rely on integrated domain counters for continuation proof. No broad result relaxation.

## Pin verification (control surfaces — unchanged; not authorizing launch)

| Subject | Expected SHA256 | Observed | Result |
| --- | --- | --- | --- |
| Commands.ps1.txt | 52E73835D67C04D2A27B047F49499C779DB3CBBAB682E485528EDA2DD1ED538C | 52E73835…ED538C | MATCH |
| VERIFICATION-ADMISSION.json | 4EEAE5B1C12F7FC6B97E00B62EAEB12CAE0F94C34A17D7E0744888367203695B | 4EEAE5B1…03695B | MATCH |
| Invoke-Verification.ps1 | 1DEA20EC5AC6C475EEEEC22EEE9B38381F31EA319B7A059409BC2BE52CE9D16B | 1DEA20EC…E9D16B | MATCH |
| packet/TIP-FREEZE.json (staged v6) | 671E008FA26ABB3EFC4BBCBB32B57C3828A50CAB2ABC343A039B29FE2F2CB599 | 671E008F…2CB599 | MATCH |
| check_t07_retirement_fake.py (staged v6) | 7CD8D26B5E402F4548E4E7DA3EFD64F6A7738D54731C6E7FEC67FE7CACB6C899 | 7CD8D26B…CB6C899 | MATCH (BLOCKED logic) |

Source pins E942 / 2E6A / 84F5 remain MATCH on staged packet. Host packet/admission/commands/wrapper were **not** edited by this review.

## Blocking findings (summary)

| ID | Control / surface | Severity |
| --- | --- | --- |
| B1 | `prior_completed` → `json.dumps` | BLOCKER |
| B2 | C-R01 `and False: pass` | BLOCKER |
| Batch-1 | C-R12 socket mutation oracle | BLOCKER |
| Batch-2 | C-PROV-BOUNDARY-ACCEPT validator not exercised | BLOCKER |
| Batch-3 | C-R10/R11 assumed later_admission + untruthful R10 stimulus wording | BLOCKER |

## Explicit non-claims / holds

- `launch_authorized=false`
- `executed=false`
- `review_only=true`
- No wrapper launch, no Python child, no imports/compile/tests, no serialization probe
- No host packet / admission / commands / wrapper mutation
- Staged v6 remains immutable; ACCEPT withdrawn
- Fresh checker successor required (authoring under existing verifier approval)
- Endpoint unbound; no retries/repairs/installs/sockets/PKI/providers/DB/Docker/native launch
- Does not claim verification PASS or full T07 / T01–T08 closure

## Confirmation

Host packet, admission, Commands, and wrapper were **not** edited. No launch performed. v1 QUALIFIED ACCEPT is superseded by this **BLOCKERS** disposition.
