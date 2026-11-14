# Jim route-fake static review — scheduler-route-fake-v1

**Attribution:** Justin under Jim (documents-only independent static review).  
**Date:** 2026-11-11  
**Disposition:** QUALIFIED ACCEPT  
**Authority:** none — `execution_authorized=false`; no `launch_authorized=true`; endpoint unbound; no Slack tip.

## Method

Ordinary file reads, `Get-FileHash` (SHA256), and UTF-8 review writes only. No imports of application/vendor packages, no compilation, no tests, no helper invocation, no source edits, no sockets/PKI/Docker/providers, no launch. Packet code was treated as data.

Working finish line folded in (read + pin only):  
`C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-investigation\Scheduler-Private-Beta-Finish-Line-Working.md`  
SHA256 `80FE8308B4D06B0D8F2D50067DBCDFB1336077E917510929946B33075A2D75EC` — **MATCH**.

Private-beta priority: concrete correctness / integration blockers first; optional compatibility/hardening staged after. Preserve access, verify-full TLS, transaction/UNKNOWN/no-retry, and cleanup protections. Do not invent new fixtures, protocol hardening, or acceptance scope.

## Reviewed input roots and Dex pins

Packet root:  
`C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-route-fake-v1\`

| Artifact | Claimed SHA256 | Observed | Result |
| --- | --- | --- | --- |
| Review-and-Commands.md | A2F994D7A85FC538F2D5C472FBF72AF8EAEA3AFD46359FD774536767BED4C2EE | same | MATCH |
| Proposed-Application.diff | 535FB0A3AFA576EB739042BDD72B707218E42D13D278E8C007B87083DC66D5A6 | same | MATCH |
| Proposed-Verification-Files.diff | 7108C445C7A844DE783C02D864079DAE6DBC95B724E9957B41AC159B528C1247 | same | MATCH |
| Commands.ps1.txt | 9E6AC4B0C103707E786997CEB1C17F98852C6E36CFF0B5A5D6C89F72B69B334F | same | MATCH |
| VERIFICATION-ADMISSION.json | BE913D81E977F9F6C35D304DE1C9EF0F1DEA75C4812007A0038A530C052E36BB | same | MATCH |
| Invoke-Verification.ps1 (wrapper, command-pinned) | 088F1BC065690FB7E33FBD91AF1388F1DD725FDA96D10CBE3747CA6908230619 | same | MATCH |

Inventory continuity (live vs admission / receipt claims):

- Packet files on disk: **475**; admission `packet_file_pin_count`: **475**; pin MATCH **475/475**; no extras, no missing, no duplicate paths.
- Partial runtime pins: **19/19** MATCH (interpreter + stdlib closure paths present).
- Application originals: **234**; candidate: **234**; byte-identical except **2** approved files; **232** other candidate files identical.
- Source inventory rows: **468** (= 234×2); verify roles: **7**; 468+7=**475**.
- Changed-byte lineage (receipt + live hashes MATCH):
  - `app/services/covering_http_transport.py` orig `E942BB43…` → cand `E2FC2226…`
  - `app/services/covering_provider_context.py` orig `875FBF61…` → cand `65529CBC…`
- Application diff is exactly the two-predicate MS exact-path correction (`kind!="oauth"/purpose!="oauth"` startswith → `kind=="event"/purpose=="event"` startswith). Candidate retains separate page-accounting branch `if purpose!="oauth":` (count=1).
- OUTER-ADMISSION subjects for admit_outer / launcher / check / EXPECTED / INPUT-MANIFEST / PACKET-SHA256SUMS MATCH live bytes. Noncircular: launcher not self-pinned in PACKET-SHA256SUMS; outer admits launcher.
- Authority flags sampled: `execution_authorized=false`, `launch_ready=false` throughout held docs. Preexisting RESULT/RECEIPT absent.

## Coverage reviewed

### 1. Source / dependency closure

Checker (`check_route.py`) AST-extracts selected definitions from original/candidate as data; injects stdlib + fake `httpx` + memory TLS factory; `JoinedTLS` live path asserts. Policy module is fully extracted (including `admit_covering_path`, `CoveringReauthorizationRequired`, counters/peers). Provider/HTTP/MS/Google symbol targets present in candidate sources by static name scan. No application/vendor package import path in the four verification roles. Runtime pin set covers interpreter + exercised stdlib modules. Compilation/exec occurs only under later authorized check (not performed here).

### 2. Oracles

`EXPECTED.json` orders **19** wire IDs. Predicates are exact nested JSON observations (bool≠int). Core MS route story is coherent with approved exact-path policy:

- Original refuses MS event overlap / event continuation; candidate admits with correct identity/event page splits.
- Identity descendants refused on candidate at client and HTTP classifiers; original still permissive (characterization).
- Explicit second identity, equal-path conflict, OAuth exact-only, Google list/events, D2 subset, and request-sharing ceiling oracles are present and internally consistent.
- Mutations: client AST revert → EVENT REFUSE; HTTP AST revert → identity-descendant OK (original bad behavior). Inventory asserts exact two-file change + corrupted synthetic pin rejection.

### 3. Actual caller / classifier composition

Controls exercise `_CoveringClient` / `CoveringHTTP.request`, `_fetch_default_calendar`, `list_microsoft_calendars`, `list_calendar_view`, Google list/paginate builders, and purpose-filtered HTTP for request-sharing second leg — not classifier-only stubs. Continuations assert absolute vs root-relative nextLink query preservation. Harness binds deadline callback identity and requires transport retirement (`close_calls==1`). Unexpected exceptions propagate (NameError/TypeError → fail, not accepted REFUSE).

### 4. Mutation / inventory controls

`ROUTE-SOURCE-INVENTORY`, `ROUTE-MUTATION-CLIENT`, `ROUTE-MUTATION-HTTP` are first-class ordered controls. Inventory rewrites only the approved predicate bytes and refuses non-approved diffs; page branch must remain. Mutations operate on in-memory AST only (commented; no source writes).

### 5. Supervision / capture / retirement

Wrapper verifies 475 packet + 19 runtime pins before Python; refuses preexisting evidence. Outer admits six subjects + interpreter, then spawns launcher under `-I -S -B` (no independent outer wait timeout — disclosed). Launcher: preexisting refuse without overwrite; exclusive `O_CREAT|O_EXCL` receipt; bounded readers (64KiB/64KiB); 30s collect + 5s kill/wait + two 5s joins; UNKNOWN on incomplete/error/alive readers; primary collection failure blocks PASS even after later exit 0; no retry/repair/fallback. Result gate requires PASS class, exact ordered wires, exact predicates, `source_hashes_verified`, `executed=true`, `inventory_error is null`.

### 6. Pin continuity

Dex root pins MATCH. Full packet pin inventory MATCH. Runtime pins MATCH. Role/manifest/sums/OUTER subjects MATCH. Commands wrapper hash MATCH. Finish-line doc MATCH.

### 7. Scope qualifications (required companions to this disposition)

These are **not** silent waivers; they bound what a later PASS may claim:

1. **19 controls ≠ 76 transport obligations.** Finite route prerequisite only. 76-entry audit is not 76 failing behaviors or 76 required new runs; evidence mapping stays Dex’s reconciliation job.
2. **Deterministic byte fakes** for framing/control-flow route classification. **Not** verify-full TLS / socket / timing proof. Do not demand native TLS repetition of every pure validator branch.
3. **Host Python 3.11** evidence is not native-runtime execution.
4. **Parser/framing completeness** and **final assembled-source coverage** for later-changed transport files remain outside this packet’s PASS claim (finish-line critical path still lists them).
5. **Outer→launcher wait** has no separate timeout; 45s is nominal collection/retirement only.
6. **Endpoint unbound**; this review is not launch, installation, profile, credential, or private-beta activation authority.
7. Finish-line preserve set (access, verify-full TLS elsewhere, transaction/UNKNOWN/no-retry, cleanup) is **retained in design** of this packet’s supervision and outcome rules; this static review does not re-prove TLS or native assessment.

## Blockers vs optional expansion

### Concrete correctness / integration blockers

**None found** that require REVISE of this held packet before a separately authorized one-shot verification card.

No pin breaks, no undeclared application mutation, no oracle/policy contradiction on the MS exact-path story, no silent `launch_authorized`/`execution_authorized`, no waiver of UNKNOWN/no-overwrite/no-retry in the four-role supervision text, and no missing extracted symbol for the declared control surface on static inspection.

### Optional expansion (after private beta / not required to accept this packet)

- Broader adversarial URL spellings beyond the included D2 subset.
- Native/TLS re-proof of pure validator branches already covered by byte fakes.
- Expanding control count toward full 76-audit enumeration as if each were a new serial gate.
- Extra fixtures, protocol hardening, or new acceptance scope beyond the two-predicate + four-role packet Trish approved for preparation.
- Public-release readiness work.

Do **not** defer a later-discovered false-success, access-boundary, transaction-integrity, or uncertain-retirement defect merely for schedule — but none such is evidenced in this static packet review.

## Disposition

**QUALIFIED ACCEPT** of the held `scheduler-route-fake-v1` packet for Jim’s documents-only review freeze.

Meaning: packet is coherent, pin-continuous, and scoped correctly for a later **separately approved** one-shot fake-route verification. Qualifications above must travel with any future launch reconciliation. This disposition does **not** authorize execution, does **not** mark Microsoft routing “shipped,” and does **not** close framing/TLS/final-integration finish-line items.

`launch_authorized` remains unset/false. No Slack tip from this seat — Jim tips after verify.
