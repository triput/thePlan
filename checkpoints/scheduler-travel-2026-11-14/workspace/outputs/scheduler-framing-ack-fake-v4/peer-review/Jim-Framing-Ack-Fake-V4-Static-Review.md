# Jim framing-ack fake-v4 static review — scheduler-framing-ack-fake-v4

**Attribution:** Justin under Jim (documents-only independent static review).  
**Date:** 2026-11-11  
**Dex assignment:** p1794461844 (ONE active; crossed reconciliation honored)  
**Disposition:** QUALIFIED ACCEPT  
**Authority:** none — `executed=false`; `execution_authorized=false`; `launch_authorized=false`; endpoint unbound; no Slack tip; no port merge.  
**Prep ≠ PASS.** This review is not a launch card.

## Method

Ordinary file reads, `Get-FileHash` (SHA256), line compare, and UTF-8 review writes only. No application/vendor imports, no compilation, no tests, no verification-helper invocation, no source/repair edits, no sockets/PKI/Docker/providers, no launch. Packet code treated as data.

## Subject vs non-subject

| Item | Role |
| --- | --- |
| `outputs/scheduler-framing-ack-fake-v4` | **Review subject** (Dex-prepared) |
| Jim v3 TIP `BD52764433172FD2FA54938C8DCA4C142C2E626DB6723AE095C2B02621773209` / check `9F2DFB45…` | **Baseline** (frozen; corrections carried forward) |
| Jim crossed prep-v4 TIP `E7150DD829640A11C50542E64F1BA921B70A9DD3B0DCE62925F3FBD1796DAE40` | **Not the subject** (preserve; do not merge) |

## Hash-verified Dex intake pins

Subject root:  
`C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-framing-ack-fake-v4\`

| Artifact | Claimed SHA256 | Observed | Result |
| --- | --- | --- | --- |
| Review-and-Commands.md | C4A4F2721791410A4A41F677C59311FEA0E983825739CCB0FBF2444EDF3C6512 | same | MATCH |
| Static-Preparation-Receipt.json | C940552B25F3FB6CEC16FBB47CBD5C00A6D9D8D07336777BC70D1455797EE114 | same | MATCH |
| Commands.ps1.txt | C2D8D18660B734EB3A6FAC9BDFACC1847C86A007C11BC81ECBEFFD1EE11FC66C | same | MATCH |
| VERIFICATION-ADMISSION.json | 4BE04F87B1AD858C05DCA789DEF05B602E80DF33274E7D19A9BB4E985B865D85 | same | MATCH |
| Proposed-Check-Fix.diff | 86EDAB63C424856C6305C244E97EE9081F0D56A22653638A011D8776F270704F | same | MATCH |
| check_framing_ack.py (v4) | 1A422FB3D669B66C2FF590C4F74F8942D23DB3811087D0E3E7B8620896477080 | same | MATCH |
| Invoke-Verification.ps1 | 0477912DBEB37067DC5CB49975A91FD1A666BD9893D166385D833D4D4E24AABA | same | MATCH |
| EXPECTED.json | 08C2367D886205C33100C8BEC6C95E5502D7AA75622B4145D77D076960F9FEA2 | same | MATCH |
| Proposed-Application.diff | 48FD631C82366BD600A87A2CC7BB3A82D4B8D36F689801E2F564EABD24BD4EFF | same as v3 | MATCH |
| base-handback TIP-FREEZE.json | BD52764433172FD2FA54938C8DCA4C142C2E626DB6723AE095C2B02621773209 | same | MATCH |

Also read: Jim-Independent-Review-Assignment.txt, Jim-Crossed-Assignment-Reconciliation.txt, Invoke-Verification.ps1, Proposed-Application.diff, packet contents, base-handback (HANDBACK / TIP / Commands-Held / role copies).

## Focus checks

### 1. One-line checker deletion only

`Compare-Object` of v3 check `9F2DFB45…` vs v4 check `1A422FB3…`: **exactly one removed line** — `"policy_pending",` inside `assert_match`'s flat runtime-field whitelist. Line counts 1057 → 1056. Proposed-Check-Fix.diff is that single hunk.

`emit_wire_candidate` still emits `"policy_pending": row["candidate"].get("policy_pending", False)` (line 706). EXPECTED.json still carries nested `policy_pending` predicates and is **byte-identical** to v3. Launcher (`invoke_framing_ack_fake.py` `7848217D…`) unchanged; still gates on exact nested `exact_predicate`. Metadata emission retained; measured flat whitelist no longer treats `policy_pending` as absent runtime data.

### 2. Concrete held operator call

v3 `Commands-Held.ps1.txt` performed wrapper/admission hash preflight and left the wrapper invocation **commented** as future shape only.

v4 `Commands.ps1.txt` (held; not invoked) contains:

- exact absolute wrapper path under fake-v4
- wrapper SHA guard `0477912D…`
- actual `& $wrapperPath -AdmissionSHA256 '4BE04F87…'`

Not a hash-only placeholder. Still marked HELD / preparation-only; no fifth executable role; wrapper bytes unchanged from v3.

### 3. Full 537 packet / 21 partial-runtime root pins

Root admission: `packet_file_pin_count=537`, `runtime_file_pin_count=21`. Live packet files on disk: **537**. Pin MATCH **537/537**; unpinned **0**; missing **0**. Runtime pins MATCH **21/21** (interpreter included); paths unique. Admission discloses partial provenance / not complete stdlib/DLL closure — truthful.

### 4. All 468 application files and 73 oracle semantics unchanged from v3

- `packet/original` + `packet/candidate`: **234 + 234 = 468**; full-tree hash compare vs prep-v3: **mismatches=0**.
- Key app pins MATCH claimed (HTTP/TLS/provider/policy).
- `EXPECTED.json` SHA MATCH v3; `wire_count=73`, `wire_ids_in_order=73`.
- `Proposed-Application.diff` byte-identical to v3 (carried framing two-file application diff; not a new application mutation in v4).

### 5. Noncircular admission

- Root `VERIFICATION-ADMISSION.json` does **not** embed its own SHA256.
- `OUTER-ADMISSION.json` (`7E81E4AD…`) subjects MATCH live admit_outer / invoke / check / EXPECTED / INPUT-MANIFEST / PACKET-SHA256SUMS; does **not** embed its own hash; does not pin root admission.
- `PACKET-SHA256SUMS.txt` (`E702BF2A…`) pins check + EXPECTED + INPUT-MANIFEST only (3 lines); does not pin itself or OUTER.
- Nested `packet/verify/VERIFICATION-ADMISSION.json` **absent** (not copied); root admission is sole operator entry. MATCH Dex claim.

### 6. Inherited bounds

Admission `supervision_limits`: 30s collect + 5s post-kill + 2×5s reader joins = 45s nominal; 64KiB/stream; 256KiB result; stop/no-overwrite/no-retry. `outer_exclusions` disclose file/hash/receipt and OS latency; no separate outer timeout. Wrapper / outer / launcher text still refuse preexisting evidence and unauthorized execution. Flags: `execution_authorized=false`, `launch_authorized=false`, `endpoint=unbound`; EXPECTED `launch_ready=false`, `executed_in_preparation=false`.

### 7. Truthful caller / native proof limits

Inherited from v3 TIP/HANDBACK and carried in Review-and-Commands:

- Native orderly-vs-abrupt TLS **unproved**.
- Historical / matched-original caller evidence ≠ new candidate owning-caller PASS.
- Header policy APPROVED remains in force; port-zero **not** merged.
- Runtime pins partial — no complete transitive closure claim.

No overclaim found in v4 prep docs relative to these limits.

### 8. Wrapper / launcher / outer code unchanged

| Role | v3 | v4 | |
| --- | --- | --- | --- |
| admit_outer.py | 26CF8FE8… | 26CF8FE8… | SAME |
| invoke_framing_ack_fake.py | 7848217D… | 7848217D… | SAME |
| Invoke-Verification.ps1 | 0477912D… | 0477912D… | SAME |
| check_framing_ack.py | 9F2DFB45… | 1A422FB3… | DIFF (intended one-line) |
| OUTER-ADMISSION.json | F14788A3… | 7E81E4AD… | DIFF (rebuilt for new check/sums) |
| PACKET-SHA256SUMS.txt | 0F08497C… | E702BF2A… | DIFF (rebuilt) |
| VERIFICATION-ADMISSION.json | 1D5847C0… | 4BE04F87… | DIFF (537-file root rebuild) |
| EXPECTED.json / INPUT-MANIFEST.json | unchanged | unchanged | SAME |

Four verification roles only; no fifth executable role introduced.

### 9. Explicit source / check / command / data diffs and pins

Present and consistent: Proposed-Application.diff (carried), Proposed-Check-Fix.diff (one-line), Commands.ps1.txt (concrete held call), rebuilt PACKET-SHA256SUMS / OUTER / root admission, receipt status `PREPARATION_COMPLETE_AWAITING_JIM_STATIC_REVIEW`.

## Blockers vs optional expansions

### Concrete correctness blockers (require REVISE before accepting this freeze)

**None found.**

The two Dex corrections (whitelist deletion; concrete held command) and the dependent pin rebuild match the assignment claims. Application/oracle bytes unchanged from v3. Admission noncircular. Nested stale admission mirror not present. Wrapper/launcher/outer code unchanged. Inherited proof limits stated truthfully. Prep flags remain non-PASS / non-launch.

### Optional expansions (not required to accept this packet freeze)

1. Native orderly-vs-abrupt TLS proof (still open; separate obligation).
2. Candidate owning-caller proof beyond matched immutable original / direct HTTP replay labeling.
3. Complete transitive stdlib/DLL runtime closure beyond the declared 21 partial pins.
4. Separate outer→launcher wall-clock timeout (currently disclosed exclusion).
5. Port-zero merge / framing assembly reconciliation (explicitly out of lane; no new authority here).
6. Launch card authoring after Trish exact-hash one-shot approval (not this seat).

## Disposition

**QUALIFIED ACCEPT** of Dex `scheduler-framing-ack-fake-v4` as a held static preparation freeze suitable for later launch-card consideration under separate Trish exact-hash authority.

Qualifications (required companions, not silent waivers):

- Preparation / this review ≠ PASS and ≠ launch authorization.
- `executed=false`; `launch_authorized=false`; endpoint unbound.
- 21 runtime pins = partial provenance.
- Native TLS orderly-vs-abrupt and candidate owning-caller remain unproved.
- Port-zero not merged; Jim crossed tip `E7150DD8…` is not this subject and was not consumed.
- No Slack tip from this seat.

## Continuity summary

| Metric | Observed |
| --- | --- |
| Intake pins (4 assigned) | 4/4 MATCH |
| Packet pins | 537/537 MATCH |
| Runtime pins | 21/21 MATCH |
| Application vs v3 | 468/468 identical |
| Oracle EXPECTED vs v3 | identical (73 controls) |
| Checker delta vs v3 | 1 line deleted (`policy_pending` whitelist) |
| Nested verify admission mirror | absent |
| Blocking findings | 0 |
| Optional expansions | 6 |
