# Jim independent static review — Dex v3 proposed runner-diagnostic diff

Prepared 2026-11-12. Reviewer seat: Justin under Jim's Dex Scheduler lane. **Docs-only / static only.** Zero execution. Zero source modifications to failed v3 packet, evidence, or tipped predecessors. Endpoint unbound. No implementation authorized. Trish combined card still pending — this review does **not** approve implementation.

## Disposition

**QUALIFIED ACCEPT** (docs/static only)

No concrete schema / privacy / exit mismatch vs immutable host validator `_record_runner_stop`. Diff is a correct narrowing of the prior design card onto the I01/I02-passed `stop_payload` body. Does not authorize runner mutation, fake authoring, or native rerun.

## Under review (hashes re-verified)

| Role | Path | Claimed SHA256 | Observed | Match |
|---|---|---|---|---|
| Proposed diff | `...\scheduler-native-provider-first-native-launch-dex-review-v2\V3-Proposed-Runner-Diagnostic.diff` | `F6135717D3DC46EB1082A19B69ECDB3602F246EFFF47FFA562E9AB1A6ECF9832` | same | YES |
| Proposal md | `...\V3-Offline-Trace-and-Diagnostic-Proposal.md` | (Dex folder) | `7328616915DAFAA0B3CF5498CD633C42E211B44E9576A3D88E9D2E86CA7EEBDE` | observed |
| Stopped runner | `...\candidate-dex-v3\payload\fixture\np_runner_entry.py` | `7FBDCAEE078CDBE3F695191ABBED93B827A31EB6FED55DCD839AB43A84355FF5` | same | YES |
| Host validator | `...\payload\fixture\docker_transport.py` | `7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53` | same | YES |
| I01/I02 precedent | `...\scheduler-native-i01-i02-v4\payload\fixture\runner_entry.py` | `2A4602CCDFA68787697ED4FD472B3BEA41FD9FC31F8F808C409339140C81FA3E` | same | YES |

Failed packet / evidence / tipped predecessors: **not mutated**.

## Checklist (Dex-named)

### ROOT / manifest alignment
- `np_runner_entry.ROOT = Path(__file__).resolve().parents[1]` → `/packet` when fixture lives at `payload/fixture/`.
- Host `docker-ops-config.json`: `source_directory` and `manifest` both under packet `payload/`; `SHA256SUMS.txt` pins use `fixture/…` relpaths.
- Diff's `stop_payload` reads `(ROOT/'SHA256SUMS.txt')` and resolves owned `.py` relpaths under ROOT — **aligned** with host owned-path checks. No host config change required.

### Cause-chain
- Walk uses `__cause__` if not None else `__context__` (I01-identical). Unhides wrapper `SuiteStop`'s underlying class when present — addresses QUALIFIED TRACE attribution gap **without** claiming which raise-site fired on the hashed 40-byte envelope.

### Bounds (3 / 8 / 128 / 4096)
- ≤3 exceptions; ≤8 frames/exception (excess frames drop oldest + `truncated=True`); traceback walk ≤128 nodes/exception; envelope UTF-8 ≤4096 bytes (trim frames or fallback). Matches host admission bounds.

### Fallback
- Any diagnostic construction failure → `return original` (`status`/`kind` only). Never replaces primary kind. Host then sets `diagnostic_unavailable=true` for status/kind-only envelopes.

### Privacy
- Location-only: path + line; sanitized kind regex. No exception args/messages, locals, SQL, request bodies, keys, certs, credentials, raw stderr, or full traceback text. Success-path `failure_evidence_limits` updated to declare optional diagnostic + caps + fallback — truthful vs behavior.

### Unchanged stop / exit behavior
- Diff preserves `status=STOP`, writes single-line JSON + `\n` to stderr, sets `_exit_code = 125`, `raise SystemExit`. No success report path introduced on STOP. Primary STOP/exit contract unchanged.

### Host validator compatibility
- Immutable `_record_runner_stop` already accepts `{status,kind}` **or** `{status,kind,diagnostic}` with `version=1`, ≤3 exceptions, ≤8 frames, manifest-owned path/line, primary-kind match. Diff targets that existing schema — **no host/helper change**.

### Primary-kind match
- Diagnostic path sets top-level `kind` via sanitized `kind(error)` and first exception entry likewise; host enforces `accepted[0]['kind'] == safe['kind']`. Fallback path has no diagnostic key, so primary-kind rule does not apply.

## Jim re-verifications (this seat)

1. Diff SHA256 = `F6135717…` — **MATCH** Dex claim.
2. Proposed `stop_payload` body (57 lines, I01 lines 532–588) is **byte-identical** to I01/I02 v4 after stripping trailing blanks (normalized SHA256 `217970A37269F418893F94B05892ABA42E4B0A428B6353959203946356655F50`). Only trailing blank-line count before `def main` differs in the hunk (diff inserts two blanks; I01 has one).
3. Diff inserts `stop_payload` immediately before `def main() -> int:` (~1349) and replaces `__main__` STOP emission with `json.dumps(stop_payload(exc), sort_keys=True)+"\n"`; updates success-path `failure_evidence_limits` accordingly.
4–6. Host accept surface, exit 125 + STOP preservation, diagnostic fallback, privacy, and cause-chain behavior — **confirmed** by static read; agree with Jim prior notes.

## Independent disagreement / alternatives (preserve)

- **Agree with Dex:** host/helper unchanged; runner-only; no root-cause repair justified from stopped record; design card → exact diff is the right narrowing.
- **Retain Jim alternative note:** static SuiteStop site-map alone cannot select which site fired on the hashed 40-byte envelope — diagnostic frames are the attribution unlock (already stated in QUALIFIED TRACE).
- **Inherited I01 qualification (not a REVISE blocker):** fallback `original` uses unsanitized `type(error).__name__` while diagnostic path sanitizes via regex; exotic names could make host refuse the fallback envelope (`runner_stop_diagnostic_refused`) while Docker failure still surfaces — same as passed I01/I02; do not expand scope to fix unless Trish asks.

## Fake-control design (docs only — do NOT author scripts)

Finite original/candidate matrix for later **Trish-approved** fake packet authoring. Fake controls use fake traceback/filesystem boundaries; existing immutable host validator exercisable with fake owned attach inputs; **no native run** in preparation/fake verification. See `Fake-Control-Design.json`.

| Control | Intent | Expectation |
|---|---|---|
| Original | status/kind-only envelope | host `diagnostic_unavailable=true` |
| Candidate happy | valid diagnostic + owned frames | host retains diagnostic |
| Cause chain | SuiteStop wrapping other class | ≥2 exception entries; primary kind=`SuiteStop` |
| Rejections | path outside ROOT; rel not in manifest; hash mismatch; line OOB | truncated and/or fallback as designed |
| Bounds | >3 exceptions, >8 frames, >4096 bytes, walk>128 | truncation flags |
| Fallback | force diagnostic failure | original status/kind only; exit still 125 |
| Privacy | inspect envelope | no exception args/messages/locals/SQL/key material |
| Unchanged stop/exit | STOP path | status=`STOP`, cli/process exit 125, no success report |

## Qualifications

1. QUALIFIED ACCEPT is docs/static only — **not** implementation authority; Trish combined card remains the implementation gate.
2. Does not attribute the stopped v3 raise-site; diagnostic frames unlock attribution only after authorized apply + run.
3. Failed v3 packet/evidence preserved; fresh-copy preparation required if/when authorized.
4. Inherited I01 fallback sanitization asymmetry retained (non-blocking).
5. Endpoint unbound; no native PASS claim.

## REVISE blockers

None found (no schema/privacy/exit mismatch vs host validator).

## Confirmations

- No imports/compilation/tests/helper/PKI/Docker/livechecks/rerun.
- No mutation of failed packet, evidence, or tipped predecessors.
- No new source or check-scripts authored for the packet (this pack is review docs only).
- Endpoint unbound; implementation not authorized.
