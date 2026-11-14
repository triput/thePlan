# Jim Host Launch Static Review v3 — scheduler-t07-fake-v2

**Reviewer:** Justin (for Jim)
**Date:** 2026-11-11
**Host dir:** C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-t07-fake-v2/
**Method:** Read-only final host launch review per Dex p1794431807. Hash-verify admission pins against staged packet / absolute runtime paths. Static-read wrapper, Review-and-Commands, Independent-Static-Review, Staging-Receipt, Host-Static-Preflight, Commands, and VERIFICATION-ADMISSION. Static-read checker for B1/B2/batch linkage. No packet edits. No imports/compile/tests. No serialization probe. No wrapper launch. No execution.
**Flags:** 
eview_only=true; xecuted=false; launch_authorized=false
**Supersedes host-review surfaces:** jim-v1 QUALIFIED ACCEPT 7B3F7104… (fake-v1 wiring) and jim-v2 BLOCKERS D58FA973… (fake-v1 checker hold). Fresh host is fake-v2 carrying reconciled v7 checker.

## Disposition

**QUALIFIED ACCEPT** — host launch surfaces are pin-consistent and gate-intact for a later Trish exact-hash one-shot card against **scheduler-t07-fake-v2**. This review does **not** authorize launch.

Blocking findings: **0**.

## Pin verification (control surfaces)

| Subject | Expected SHA256 | Observed | Result |
| --- | --- | --- | --- |
| Commands.ps1.txt | 3432F0E35D2D24CCC704423299B656A1BB275705AA95D68B431630649948D10C | 3432F0E35D2D24CCC704423299B656A1BB275705AA95D68B431630649948D10C | MATCH |
| VERIFICATION-ADMISSION.json | 903FFC3D9EE425027FDBBD97EE265E3D3A1AB822D2508819BB2D3C783DD636D2 | 903FFC3D9EE425027FDBBD97EE265E3D3A1AB822D2508819BB2D3C783DD636D2 | MATCH |
| Invoke-Verification.ps1 | 1DEA20EC5AC6C475EEEEC22EEE9B38381F31EA319B7A059409BC2BE52CE9D16B | 1DEA20EC5AC6C475EEEEC22EEE9B38381F31EA319B7A059409BC2BE52CE9D16B | MATCH (unchanged; prior Jim NO_BLOCKER) |
| packet/TIP-FREEZE.json (accepted v7) | 19A9BE6B465CA7041231846687F85E950ED5AD0CB02C6318C93CA985E2EE63B1 | 19A9BE6B465CA7041231846687F85E950ED5AD0CB02C6318C93CA985E2EE63B1 | MATCH |
| check_t07_retirement_fake.py | C8C1915AF1A2A8314BFE2A80B61B1FDA6708F9001C59CB1EC25C9410887BF19F | C8C1915AF1A2A8314BFE2A80B61B1FDA6708F9001C59CB1EC25C9410887BF19F | MATCH |
| EXPECTED-OUTPUT.json | E03E597528AEB9251AF39B975EFFCD1EF85C5F777F6D55F37E46BBC98A72A10A | E03E597528AEB9251AF39B975EFFCD1EF85C5F777F6D55F37E46BBC98A72A10A | MATCH |
| INPUT-MANIFEST.json | 27E8AD93F6D57994087038C735849F69C34FDC1D098D2905029605CD15E09623 | 27E8AD93F6D57994087038C735849F69C34FDC1D098D2905029605CD15E09623 | MATCH |
| OUTER-ADMISSION.json | 403E5EC53B34D41D43FE0A90E00801EC38F1BEC83CC3E9C243093649B5310074 | 403E5EC53B34D41D43FE0A90E00801EC38F1BEC83CC3E9C243093649B5310074 | MATCH |

### Accepted v7 source linkage (workspace pins)

| Source | Expected | Staged packet path | Result |
| --- | --- | --- | --- |
| covering_http_transport.py | E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD | payload/workspace/apps/api/app/services/… | MATCH |
| covering_joined_https.py | 2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B | payload/workspace/apps/api/app/services/… | MATCH |
| covering_refresh_import.py | 84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339 | payload/workspace/apps/api/app/services/… | MATCH |

## Commands / wrapper / admission kind

- Commands.ps1.txt is exactly one line invoking Invoke-Verification.ps1 with -AdmissionSHA256 '903FFC3D…D636D2' (byte-exact vs Review-and-Commands.md fence and Staging-Receipt.command).
- Wrapper requires live admission SHA match before any child; kind must equal scheduler-t07-one-shot-fake-verification-admission.
- Staged admission kind matches. Wrapper SHA unchanged from prior reviewed T07 wrapper (1DEA20EC…); control-flow gates unchanged (relative_path / absolute_path inventories; refuse existing evidence; single -I -S -B admit_outer.py).

## Packet + runtime pin counts (hash-verified)

| Inventory | Declared count | Array length | Staged/live files | Hash-OK | Escape/dup | Missing/unpinned |
| --- | --- | --- | --- | --- | --- | --- |
| packet_files (
elative_path) | 253 | 253 | 253 on disk under packet/; 0 unpinned extras | **253/253** | 0 | 0 |
| runtime_files (bsolute_path) | 17 | 17 | all absolute paths present | **17/17** | 0 | 0 |

- Interpreter C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe is included in runtime inventory.
- Host-Static-Preflight.json reports the same 253/17, 41 controls, 31 PASS / 10 PASS_WITNESS, xecution_performed=false, xecution_authorized=false, peer_host_review=pending (this review).
- Independent-Static-Review.json records Dex acceptance of v7 for renewed bounded fake-only launch review; closed_v6_findings list matches B1/B2/batch; xecution_authorized=false.
- EXPECTED-OUTPUT.json independently recounts **31 PASS** + **10 PASS_WITNESS** across the ordered 41-control object (control_ids_in_order ↔ controls keys exact).

## Corrected result projection / assertion linkage (static read of v7 checker)

Observed in pinned check_t07_retirement_fake.py (C8C1915A…) — no execution:

1. **B1:** project_completed_result_evidence + ssert_sub1_prior_success; prior_completed evidence is primitive projection; originals retained for behavior asserts; prior_completed_sub1_ok asserted on caller controls. nd False / default=str appear only in comments/docstrings forbidding those patterns — not live disable.
2. **B2 / C-R01:** asserts exactly 1 
esponse_close_calls + 1 method_close_calls + valid returned result (status 200 / non-empty content).
3. **C-R12:** instrumented fake socket; asserts closed/owner/socket identity unchanged + zero raw close under explicit fake-thread scope.
4. **C-PROV-BOUNDARY-ACCEPT:** calls ssert_provenance_boundary on valid representative UNKNOWN inputs (plus reject paths).
5. **C-R10/R11:** stimulus labeled complete_http_500_server_error_json; malformed_lost_response_obligation=open_not_this_control; no assumed later_admission measurement.

## Fresh evidence paths

Under packet/fake-only-t07-retirement-verification/:

- FAKE-T07-RESULT.json — **absent**
- FAKE-T07-LAUNCH-RECEIPT.json — **absent**

Wrapper refuse-on-existing-evidence gate remains intact; no replay surface present.

## 45s nominal retirement / capture limits

Disclosed consistently as **30 + 5 + 5 + 5 = 45** seconds nominal collection/retirement (excluding outer hash/file ops and OS latency):

| Surface | child_wait | post_kill | reader_join each | Nominal total |
| --- | --- | --- | --- | --- |
| Review-and-Commands.md | 30s | 5s | 5s ×2 | 45s |
| INPUT-MANIFEST.json held_launcher_limits | 30 | 5 | 5 | 45 |
| invoke_t07_fake.py constants + docstring | TIMEOUT=30 | POST_KILL=5 | READER_JOIN=5 | 45 |

Capture caps (64 KiB stdout/stderr, 256 KiB result) match Review-and-Commands.md and INPUT-MANIFEST.

Note (qualification, not blocker): host VERIFICATION-ADMISSION.json is pin-inventory only and does not re-embed timeout scalars; limits are carried by the pinned inner manifest/launcher and the held launch doc.

## Truthful proof boundaries

Observed and consistent across Review-and-Commands.md, Independent-Static-Review.json, TIP-FREEZE v7, and harness docs:

- Fake native/DB/parent/transaction/session, budget clocks, sockets/TLS, ownership identities.
- Selected extracted definitions only; not whole-app import.
- OAuth control = extracted Google 
efresh_access_token path; not make_domain_ports.token policy/terminal or account persistence.
- Event witness = selected owning importer try/except; not full setup/post-fetch.
- Does **not** close full T07 or T01–T08; does not establish real provider retirement or replace native integration evidence.
- Runtime pins = explicit interpreter/stdlib subset (prior 12 + copy/enum/datetime/pathlib/typing); **not** a complete runtime dependency closure (disclosed).
- Open (documented, not blockers for this bounded fake): distinct malformed-response and lost-response transport proofs (EXPECTED.open_obligations).

## Wrapper containment gates (static re-read)

Same gates as prior Jim wrapper NO_BLOCKER (Jim-Static-Read-Invoke-Verification.md SHA 94D7F331…), confirmed against live wrapper bytes 1DEA20EC…:

1. Mandatory 64-hex AdmissionSHA256; live admission hash before interpret.
2. Exact T07 admission kind.
3. Packet pin count consistency; 
elative_path + 64-hex; under $packetRoot prefix; HashSet rejects duplicates; live hash match.
4. Runtime pin count consistency; bsolute_path rooted; HashSet rejects duplicates; live hash match.
5. Interpreter must appear in runtime inventory.
6. Refuse existing FAKE-T07 result/receipt.
7. Single Python spawn: -I -S -B admit_outer.py; non-zero → STOP; no retry/repair.

Live pin pass exercised those containment/count/duplicate/hash rules without invoking the wrapper process as a launch.

## Qualifications (non-blocking)

1. Host admission JSON omits timeout scalars (limits live in pinned INPUT-MANIFEST + invoke + Review-and-Commands) — consistent, inventory-shaped.
2. Runtime inventory is partial by design — disclosed; not an immutable-FS claim.
3. Malformed/lost-response transport proofs remain open obligations — documented; not in this 41-control bounded fake scope.
4. Peer preflight still marked peer_host_review=pending until Dex reconciles this note.
5. Predecessor fake-v1 / v6 hold packets remain preserved/immutable; this review does not reopen them.

## Blocking findings

None.

## Explicit non-claims / holds

- launch_authorized=false
- xecuted=false
- 
eview_only=true
- No wrapper launch, no Python child, no imports/compile/tests, no serialization probe, no packet/admission/commands mutation by this review.
- Endpoint unbound; no retries/repairs/installs/sockets/PKI/providers/DB/Docker/native launch.
- Qualified accept of host static readiness for Dex→Trish card prep only — not a verification PASS and not full T07/T01–T08 closure.
- Preserved predecessors: scheduler-t07-fake-v1, jim host-review v1/v2, checker v6/v7 tipped packets.

## Confirmation

Host packet, admission, Commands, and wrapper were **not** edited. No launch performed.
