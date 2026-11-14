# Fake-only T07 retirement verification — REVIEW (authoring, not executed)

Status: AUTHORING ONLY / PREPARATION. `launch_ready=false`. `executed_in_preparation=false`.
No check invocation, admit/launcher run, app imports, compilation, sockets, providers, credentials, PKI, Docker/native continuation, deployment, or endpoint binding occurred in this preparation packet. D2 one-shot was not launched.

## Authority
- Approval: Trish “Approved for both D2 and T07” (`Approval-D2-and-T07-20261111.json`)
- Scope: `T07-Preparation-Scope-For-Approval.md` SHA256 `B1481463CA6993C6C4C884485237E5DD2C308B7578A796DE5DE89565BDD46C83`
- Design TIP v3: `94362F46EE6912A9A6F2A7CB64A673E51A2037D145A1FB70721F373FE2B7AA91`
- Exact diff: `8623F550F8B0BE9DFA00EBD8AD066768F22BE0750DC3DD635CF0A2F7A4CE7808`

## Source (fresh copy only)
Parent packet applies the reviewed three-file diff to a new 234-file API copy.
Originals preserved under `payload/bases/app/services/`:
| File | Base SHA256 |
| --- | --- |
| covering_http_transport.py | `AECE10186CFFAE46D3EF2292D3772F1C287FD0A562AA9E764AAC4ABB10C861D8` |
| covering_joined_https.py | `C58382900BE1C190ED39242B4992FE88E1155E55F7E8C33D32065DBFCC993468` |
| covering_refresh_import.py | `C57A5F956BEA5A364B781C586B595C984013F357F337355B30C4182230BFE1F0` |

Resulting candidate hashes (must match):
| File | SHA256 |
| --- | --- |
| covering_http_transport.py | `E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD` |
| covering_joined_https.py | `2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B` |
| covering_refresh_import.py | `84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339` |

Note: `covering_refresh_import.py` original base is CRLF; Dex prospective pin is LF-normalized candidate bytes. Candidate written as LF to match the required resulting hash. D2 packet and design predecessors untouched.

## Executable-wrapper delta vs D2
Reuses the reviewed bounded admit → launcher → check pattern from
`post-native-d2-source-fake-prep-jim-v4-ms-context-2026-11-11/fake-only-d2-path-admission-verification/`.
Delta: renamed entry/result/receipt/class labels only
(`check_t07_retirement_fake.py`, `invoke_t07_fake.py`, `FAKE-T07-RESULT.json`,
`FAKE-T07-LAUNCH-RECEIPT.json`, class `FAKE-T07-RETIREMENT`). Same isolation pins,
capture limits, and noncircular hash scheme.

## Named controls (39)
- Candidate functional (22): C-R01–C-R12, C-OUT-VE, C-OUT-UNK, C-UNK-PULL, C-CALLER-EVENT/OAUTH/IDENTITY, C-NO-LATER-ADMISSION, C-POS-KNOWN-REAUTH, C-PROV-BOUNDARY-ACCEPT/REJECT
- Original designated witnesses (9): O-R02, O-R03-EV, O-R04, O-R05, O-R06, O-R08, O-UNK-PULL, O-ID-OS, O-R11 — exact expected observations; arbitrary failures/unexpected UNKNOWN do not PASS
- Mutations (3, harness-only in-memory): M-SKIP-SECOND-CLOSE, M-AMBIENT-EXC-INFO, M-MUTATE-OUTER-UNKNOWN
- Inventory self-checks (5): H-INVENTORY-ACCEPTS-GOOD / REJECTS-MISSING / DUPLICATE / REORDER / ALTERED
- Functional total 31 = 22 candidate + 9 original witnesses
- **C-OUT-VE** and **C-OUT-UNK** present

## Extraction / fake deps
AST-extracts candidate CoveringHTTP / JoinedTLS / CoveringRootOutcomeUnknown / policy helpers and original bases for contract-miss witnesses. Fully fake owned byte/socket/response, clock, owner-ID, caller/role deps. Bounded fixed-field sanitized evidence (classes/packet-owned labels only). No raw messages/locals/SQL/credentials/URLs/provider bodies. Finite production provenance-boundary inventory; unexpected occurrence shapes rejected. Fake owner ID / terminal ack / retirement result labeled with explicit proof limits; no actual threads/sockets.

## R11
Complete invalid_grant + uncertain retirement → UNKNOWN / no-later-admission (inherited contract).

## Held launcher limits (documented; not run)
- One pinned Python invocation (`admit_outer.py` → `invoke_t07_fake.py` → check)
- 30s child wait, 5s termination/wait, two 5s reader joins
- 64 KiB stdout/stderr each, 256 KiB result
- Interpreter pin: `C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe` SHA256 `5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC`

## Explicitly NOT claimed
- Full T01–T08 closure
- Real TLS / provider dial / endpoint or profile binding
- Provider retirement via fake DB rollback
- Execution authority (`launch_ready` remains false)

## Untouched
- D2 packet / pending D2 card / D2 one-shot
- T07 design predecessors (v1/v2/v3)
- Original immutable scheduler-d2-fake-v1 API tree
