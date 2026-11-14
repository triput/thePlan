# Jim Host Launch Static Review — scheduler-t07-fake-v1

**Reviewer:** Justin (for Jim)
**Date:** 2026-11-11
**Host dir:** `C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-t07-fake-v1/`
**Method:** Read-only static host launch review. Hash-verify admission pins against staged packet / absolute runtime paths. No packet edits. No imports/compile/tests. No wrapper launch. No execution.
**Flags:** `review_only=true`; `executed=false`; `launch_authorized=false`

## Disposition

**QUALIFIED ACCEPT** — host launch surfaces are pin-consistent and gate-intact for a later Trish exact-hash one-shot card. This review does **not** authorize launch.

Blocking findings: **0**.

## Pin verification (control surfaces)

| Subject | Expected SHA256 | Observed | Result |
| --- | --- | --- | --- |
| Commands.ps1.txt | 52E73835D67C04D2A27B047F49499C779DB3CBBAB682E485528EDA2DD1ED538C | 52E73835D67C04D2A27B047F49499C779DB3CBBAB682E485528EDA2DD1ED538C | MATCH |
| VERIFICATION-ADMISSION.json | 4EEAE5B1C12F7FC6B97E00B62EAEB12CAE0F94C34A17D7E0744888367203695B | 4EEAE5B1C12F7FC6B97E00B62EAEB12CAE0F94C34A17D7E0744888367203695B | MATCH |
| Invoke-Verification.ps1 | 1DEA20EC5AC6C475EEEEC22EEE9B38381F31EA319B7A059409BC2BE52CE9D16B | 1DEA20EC5AC6C475EEEEC22EEE9B38381F31EA319B7A059409BC2BE52CE9D16B | MATCH (prior Jim NO_BLOCKER) |
| packet/TIP-FREEZE.json (accepted v6) | 671E008FA26ABB3EFC4BBCBB32B57C3828A50CAB2ABC343A039B29FE2F2CB599 | 671E008FA26ABB3EFC4BBCBB32B57C3828A50CAB2ABC343A039B29FE2F2CB599 | MATCH |
| check_t07_retirement_fake.py | 7CD8D26B5E402F4548E4E7DA3EFD64F6A7738D54731C6E7FEC67FE7CACB6C899 | 7CD8D26B5E402F4548E4E7DA3EFD64F6A7738D54731C6E7FEC67FE7CACB6C899 | MATCH |
| EXPECTED-OUTPUT.json | AD4B9F38A95BB80929806F54994C0C7A13ED3AE580CB662681400238AD4F5110 | AD4B9F38A95BB80929806F54994C0C7A13ED3AE580CB662681400238AD4F5110 | MATCH |
| INPUT-MANIFEST.json | A9DD0588E6F99EB57DC4EB5F9F030136EC6790D0063091BD3C29FD3C20772255 | A9DD0588E6F99EB57DC4EB5F9F030136EC6790D0063091BD3C29FD3C20772255 | MATCH |
| OUTER-ADMISSION.json | E937357ACED10BD87DD91C7A57036F5B7490F8200933C58740D607687BFA8867 | E937357ACED10BD87DD91C7A57036F5B7490F8200933C58740D607687BFA8867 | MATCH |

### Accepted v6 source linkage (workspace pins)

| Source | Expected | Staged packet path | Result |
| --- | --- | --- | --- |
| covering_http_transport.py | E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD | payload/workspace/apps/api/app/services/… | MATCH |
| covering_joined_https.py | 2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B | payload/workspace/apps/api/app/services/… | MATCH |
| covering_refresh_import.py | 84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339 | payload/workspace/apps/api/app/services/… | MATCH |

`payload/bases/…` copies retain distinct original-reference digests (AECE/C583/C57A) and are separately pinned; that split matches TIP/INPUT-MANIFEST and is not a mismatch.

## Commands / wrapper / admission kind

- `Commands.ps1.txt` is exactly one line invoking `Invoke-Verification.ps1` with `-AdmissionSHA256 '4EEAE5B1…3695B'` (byte-exact vs Review-and-Commands.md).
- Wrapper requires live admission SHA match before any child; `kind` must equal `scheduler-t07-one-shot-fake-verification-admission`.
- Staged admission `kind` matches. Wrapper-Preparation.json records the same wrapper SHA and T07 label substitutions; `control_flow_changed=false`.

## Packet + runtime pin counts (hash-verified)

| Inventory | Declared count | Array length | Staged/live files | Hash-OK | Escape/dup | Missing |
| --- | --- | --- | --- | --- | --- | --- |
| packet_files | 253 | 253 | 253 on disk under `packet/`; 0 unpinned extras | **253/253** | 0 | 0 |
| runtime_files | 17 | 17 | all absolute paths present | **17/17** | 0 | 0 |

- Interpreter `C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe` is included in runtime inventory.
- Host-Static-Preflight.json reports the same 253/17, 41 controls, 31 PASS / 10 PASS_WITNESS, `execution_performed=false`, `execution_authorized=false`, `peer_host_review=pending` (this review).
- EXPECTED-OUTPUT.json independently recounts **31 PASS** + **10 PASS_WITNESS** across the ordered 41-control object.

## Fresh evidence paths

Under `packet/fake-only-t07-retirement-verification/`:

- `FAKE-T07-RESULT.json` — **absent**
- `FAKE-T07-LAUNCH-RECEIPT.json` — **absent**

Wrapper refuse-on-existing-evidence gate remains intact; no replay surface present.

## 45s nominal retirement / capture limits

Disclosed consistently as **30 + 5 + 5 + 5 = 45** seconds nominal collection/retirement (excluding outer hash/file ops and OS latency):

| Surface | child_wait | post_kill | reader_join each | Nominal total |
| --- | --- | --- | --- | --- |
| Review-and-Commands.md | 30s | 5s | 5s ×2 | 45s |
| INPUT-MANIFEST.json `held_launcher_limits` | 30 | 5 | 5 | 45 |
| invoke_t07_fake.py constants + docstring | TIMEOUT=30 | POST_KILL=5 | READER_JOIN=5 | 45 |

Capture caps (64 KiB stdout/stderr, 256 KiB result) match Review-and-Commands.md and INPUT-MANIFEST.

Note (qualification, not blocker): host `VERIFICATION-ADMISSION.json` is pin-inventory only and does not re-embed timeout scalars; limits are carried by the pinned inner manifest/launcher and the held launch doc.

## Truthful proof boundaries

Observed and consistent across Review-and-Commands.md, Frozen-Source-Fake-v6-Review.json, TIP-FREEZE, and harness docs:

- Fake native/DB/parent/transaction/session, budget clocks, sockets/TLS, ownership identities.
- Selected extracted definitions only; not whole-app import.
- OAuth control = extracted Google `refresh_access_token` path; not `make_domain_ports.token` policy/terminal or account persistence.
- Event witness = selected owning importer try/except; not full setup/post-fetch.
- Does **not** close full T07 or T01–T08; does not establish real provider retirement or replace native integration evidence.
- Runtime pins = explicit interpreter/stdlib subset (prior 12 + copy/enum/datetime/pathlib/typing); **not** a complete runtime dependency closure (disclosed).

## Wrapper containment gates (static re-read)

Same gates as prior Jim wrapper NO_BLOCKER (`Jim-Static-Read-Invoke-Verification.md` SHA 94D7F331…):

1. Mandatory 64-hex AdmissionSHA256; live admission hash before interpret.
2. Exact T07 admission kind.
3. Packet pin count consistency; relative path + 64-hex; under `$packetRoot` prefix; HashSet rejects duplicates; live hash match.
4. Runtime pin count consistency; absolute rooted paths; HashSet rejects duplicates; live hash match.
5. Interpreter must appear in runtime inventory.
6. Refuse existing FAKE-T07 result/receipt.
7. Single Python spawn: `-I -S -B admit_outer.py`; non-zero → STOP; no retry/repair.

Live pin pass exercised those containment/count/duplicate/hash rules without invoking the wrapper process as a launch.

## Qualifications (non-blocking)

1. Host admission JSON omits timeout scalars (limits live in pinned INPUT-MANIFEST + invoke + Review-and-Commands) — consistent, inventory-shaped.
2. Runtime inventory is partial by design — disclosed; not an immutable-FS claim.
3. Earlier `Host-Admission-Static-Review.json` text saying admission was unstaged is chronological residue; current host has staged admission SHA 4EEAE5B1… and matching Commands — do not treat the older note as a live blocker.
4. Peer preflight still marked `peer_host_review=pending` until Dex reconciles this note.

## Blocking findings

None.

## Explicit non-claims / holds

- `launch_authorized=false`
- `executed=false`
- `review_only=true`
- No wrapper launch, no Python child, no imports/compile/tests, no packet/admission/commands mutation by this review.
- Endpoint unbound; no retries/repairs/installs/sockets/PKI/providers/DB/Docker/native launch.
- Qualified accept of host static readiness for Dex→Trish card prep only — not a verification PASS and not full T07/T01–T08 closure.

## Confirmation

Host packet, admission, Commands, and wrapper were **not** edited. No launch performed.
