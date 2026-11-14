# Jim port-zero fake static review — scheduler-port-zero-fake-v1

**Attribution:** Justin under Jim (documents-only independent static review).  
**Date:** 2026-11-11  
**Disposition:** QUALIFIED ACCEPT  
**Authority:** none — `executed=false`; `execution_authorized=false`; `launch_authorized=false`; endpoint unbound; no Slack tip.  
**Sequencing:** After framing-ack prep v2 (frozen/tipped separately). Do **not** merge into framing. Preparation is **not** PASS.

## Method

Ordinary file reads, `Get-FileHash` (SHA256), and UTF-8 review writes only. No imports of application/vendor packages, no compilation, no tests, no helper invocation, no source/repair edits, no sockets/PKI/Docker/providers, no launch. Packet code was treated as data.

Working finish line folded in (read + pin only):  
`C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-investigation\Scheduler-Private-Beta-Finish-Line-Working.md`  
SHA256 `80FE8308B4D06B0D8F2D50067DBCDFB1336077E917510929946B33075A2D75EC` — **MATCH**.

Related proposal / framing note (context only, not this packet’s authority):
- Trish prep approval scope SHA256 `A27E47A5B7106708CC1A6E683D645CAB2821FBA1FAE2F45E7A7488F1DB5B0F85` MATCH vs `scheduler-port-zero-proposal-v1/Preparation-Scope-For-Approval.md`
- Approved proposed-fix / application diff SHA256 `C69EB5EFFAD47FBC1BB2A085DCF7620D736EF713BC09B4D4984736104BC9F8CB` MATCH (proposal `Proposed-Fix.diff` ≡ packet `Proposed-Application.diff`)
- Framing v2 port-zero static source note remains non-implementing documentation; this packet is the held preparation under separate Trish prep approval (`call_b66df08912ce4e8399ea9e7bf60ee8e2`).

## Reviewed input roots and Dex pins

Packet root:  
`C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-port-zero-fake-v1\`

| Artifact | Claimed SHA256 | Observed | Result |
| --- | --- | --- | --- |
| Commands.ps1.txt | A98838452A0E7B6FA5BA504E38F2BA54E05890DFC759D33AE23412F94D87E048 | same | MATCH |
| VERIFICATION-ADMISSION.json | AE502E6BAA2CF8CA33B9E1137E5BB8C5E5FCC14F620239914DB3CAFCE1E86532 | same | MATCH |
| Invoke-Verification.ps1 (wrapper) | DEBB3731B4C76DDA38AC3D32FD582A3EE5D121D5E6850757D07E5172B2C232D6 | same | MATCH |
| Proposed-Application.diff | C69EB5EFFAD47FBC1BB2A085DCF7620D736EF713BC09B4D4984736104BC9F8CB | same | MATCH |
| Review-and-Commands.md | (live) EBEBAFA978FEA6DE574F5037F1A3B72B2581442725B64CE42501CE9A69C63661 | recorded | PINNED |
| Proposed-Verification-Files.diff | (live) BD2479B0E0C72D0369D62F99B58D63E77143800C84378B2E3E75B26D3370277C | recorded | PINNED |
| Static-Preparation-Receipt.json | (live) 0576FC98E1CA78A76C51C5B3D4DF1B90792664693934299DC5BFAB0FFC6C39F6 | recorded | PINNED |
| policy original | A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598 | same | MATCH |
| policy candidate | 5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88 | same | MATCH |

Inventory continuity (live vs admission / receipt claims):

- Packet files on disk: **475**; admission `packet_file_pin_count`: **475**; pin MATCH **475/475**; no extras, no missing, no duplicate paths.
- Partial runtime pins: **19/19** MATCH (interpreter + disclosed stdlib closure paths present).
- Application originals: **234**; candidate: **234**; byte-identical except **1** approved file; **233** other candidate files identical.
- Source inventory rows: **468** (= 234×2); verify roles: **7**; 468+7=**475**.
- Changed-byte lineage: `app/services/covering_transport_policy.py` only; single expression  
  `(u.port or 443)==self.port` → `(443 if u.port is None else u.port)==self.port`.  
  OLD count orig=1/cand=0; NEW count orig=0/cand=1; `orig.replace(OLD,NEW)==cand` True.
- Lineage to passed route candidate: port **original** ≡ `scheduler-route-fake-v1` **candidate** for **234/234** files (including route-changed HTTP/provider files and unchanged policy `A265F81F…`).
- OUTER-ADMISSION subjects for admit_outer / launcher / check / EXPECTED / INPUT-MANIFEST / PACKET-SHA256SUMS MATCH live bytes. Noncircular: PACKET-SHA256SUMS pins check/EXPECTED/INPUT-MANIFEST only; launcher and admit_outer are not self-pinned there; outer admits itself + launcher from independently root-pinned OUTER-ADMISSION.
- Authority flags sampled: no `execution_authorized=true` / `launch_authorized=true` / `launch_ready=true` in held root docs. Preexisting RESULT/RECEIPT absent.

## Coverage reviewed

### 1. Source lineage

Both 234-file application trees derive from the passed routing candidate. Port original is byte-identical to that route candidate. Port candidate differs only in the approved one-expression policy edit. Application diff equals the Trish-approved proposal fix bytes. No framing-source merge is claimed or observed.

### 2. Explicit 0 witness / nondefault-port positives / refusals

`EXPECTED.json` orders **9** wire IDs. Seven original/candidate HTTPSPeer cases:

| ID | Peer | URL | Original | Candidate |
| --- | --- | --- | --- | --- |
| PORT-443-ABSENT | 443 | absent port | ACCEPTED (parsed null) | ACCEPTED (parsed null) |
| PORT-443-EXPLICIT | 443 | `:443` | ACCEPTED | ACCEPTED |
| PORT-443-ZERO | 443 | `:0` | ACCEPTED (parsed 0) — **witness** | REFUSED |
| PORT-443-OTHER | 443 | `:444` | REFUSED | REFUSED |
| PORT-8443-ABSENT | 8443 | absent | REFUSED | REFUSED |
| PORT-8443-EXPLICIT | 8443 | `:8443` | ACCEPTED | ACCEPTED |
| PORT-8443-ZERO | 8443 | `:0` | REFUSED | REFUSED |

Static semantics of the expressions match these oracles: falsy `u.port==0` collapses to 443 under original; candidate treats explicit 0 as 0. Peer `__post_init__` still requires `1 <= self.port <= 65535` on both sides (peer cannot be configured as 0).

### 3. Actual urlsplit / class extraction

`check_port.py` AST-extracts only `HTTPSPeer` from original/candidate policy bytes; injects stdlib `dataclass` / `ip_address` / host `urllib.parse.urlsplit` and a local fake `CoveringTransportRefused`. No application/vendor package imports in the four verification roles. Inventory/mutation controls enforce the exact OLD→NEW expression and refuse a corrupted source pin (`PORT-BAD-PIN`).

### 4. Exact oracle admission

Launcher loads `EXPECTED.json` and gates PASS on status class, exact ordered wire IDs, exact nested observation predicates, `source_hashes_verified`, `executed=true`, and `inventory_error is null`. Exit-0 alone cannot PASS. Checker writes exclusive result; wrapper and launcher refuse preexisting evidence.

### 5. Noncircular pins

Wrapper admits whole packet/runtime before Python. Outer admits interpreter + six subjects from OUTER-ADMISSION (not embedding its own hash in PACKET-SHA256SUMS). Launcher admits checker/expected/input manifest via PACKET-SHA256SUMS. No circular embedded self hashes observed.

### 6. Inherited supervision / retirement bounds

Roles: `check_port.py`, `invoke_port_fake.py`, `admit_outer.py`, `Invoke-Verification.ps1`. Launcher/outer adapted from passed routing packet with role/result labels changed; supervision/capture retained: 64KiB stdout/stderr, 256KiB result; 30s collect + 5s kill/wait + two 5s reader joins = 45s nominal; UNKNOWN on incomplete/error/alive readers; primary collection failure blocks PASS even after later exit 0; no retry/repair/fallback; exclusive `O_CREAT|O_EXCL` receipt. Outer→launcher wait has no separate timeout (disclosed). Isolation `-I -S -B` required.

### 7. One policy expression only / both 234-file copies / 9 controls / 475+19 pins

All verified live as above. Receipt claims (`controls_authored=9`, `packet_pins_checked=475`, `runtime_pins_checked=19`, `application_files_per_side=234`, `changed_files=[covering_transport_policy.py]`) MATCH observed inventory.

## Scope qualifications (required companions to this disposition)

These are **not** silent waivers; they bound what a later PASS may claim:

1. **9 controls ≠ full transport / dial / TLS closure.** Finite exact-port admission prerequisite only.
2. **Deterministic byte/class extraction** for origin-port admission. **Not** verify-full TLS / socket / timing / dial-destination proof. Dial remains pinned numeric peer/port; this packet does not claim connect behavior.
3. **Host Python 3.11** evidence is not native-runtime execution.
4. **19 runtime pins** are partial provenance, not transitive stdlib/DLL closure (admission already discloses this).
5. **Outer→launcher wait** has no separate timeout; 45s is nominal collection/retirement only.
6. **Do not merge into framing** until separately authorized verification reconciles. Framing OWS / ack lane stays independent.
7. **Endpoint unbound**; this review is not launch, installation, profile, credential, or private-beta activation authority.
8. Preparation / this static review ≠ PASS and ≠ launch card.

## Blockers vs optional expansion

### Concrete correctness / integration blockers

**None found** that require REVISE of this held packet before a separately authorized one-shot verification card.

No pin breaks, no undeclared application mutation, no oracle/policy contradiction on the explicit-0 / nondefault-port story, no silent `launch_authorized`/`execution_authorized`, no waiver of UNKNOWN/no-overwrite/no-retry in the four-role supervision text, lineage to route candidate intact, and checker extracts the declared class with host urlsplit only.

### Optional expansion (not required to accept this packet)

- Additional adversarial URL spellings beyond the seven peer/url cases.
- Native/TLS re-proof of this pure validator branch.
- Expanding beyond one-expression admission into dial/TLS destination claims.
- Merging the candidate policy into a final framing-assembled tree (separate reconciliation after verify).

## Disposition

**QUALIFIED ACCEPT** of the held `scheduler-port-zero-fake-v1` packet for Jim’s documents-only review freeze.

Meaning: packet is coherent, pin-continuous, lineage-correct from the passed route candidate, and scoped correctly for a later **separately approved** one-shot fake-port verification. Qualifications above must travel with any future launch reconciliation. This disposition does **not** authorize execution, does **not** mark port-zero admission “shipped,” and does **not** authorize framing merge.

`executed=false`. `launch_authorized=false`. No Slack tip from this seat — Jim tips after verify (if/when authorized).
