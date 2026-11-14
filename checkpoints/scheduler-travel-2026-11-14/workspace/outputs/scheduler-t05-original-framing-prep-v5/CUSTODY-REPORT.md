# T05 fake framing prep v5 — authoring custody

## Immutable predecessors
- v1 / v2 / v3 / **v4** prep packets untouched (v4 tip `A40F0DEA…` / admission `D7F0A162…` / check `755181B7…` remain frozen REVISE).
- Dex `native-dex-*` dirs untouched; B8 deferred to Dex.

## v1 helper compile receipt (preserved; do not delete/run)
| Field | Value |
| --- | --- |
| Path | `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-t05-original-framing-prep-v1\__pycache__\_prep_build_only.cpython-311.pyc` |
| SHA256 | `72615E8E4EABB57A9032EF695B2752139E1BCFE42759560A4C71AB5E35AE12CC` |
| Bytes | 29470 |
| mtime UTC | 2026-11-11T21:54:19.0696255Z |
| Stated authoring command in prior custody | `python -I -S -B _prep_build_only.py` |
| Honesty (P5) | **`-B` suppresses ordinary automatic bytecode writes.** That stated command does **not** by itself explain this retained pyc. Exact compile/write command that produced the pyc is **UNKNOWN** from verified receipts. Possible histories include an explicit `compile`/`py_compile` step, a run without `-B`, or another unrecollected authoring action. Recollection that “implicit compile produced the pyc during that authoring pass” is **recollection, not a verified execution receipt**. |
| Meaning | Helper compilation for wire/manifest **authoring** in v1 — **not** checker/invoke/admit/wrapper/Docker execution. **Do not rerun** to reconstruct evidence. |

## `_refreeze.py`
| Field | Value |
| --- | --- |
| Observed on v3 | `...\scheduler-t05-original-framing-prep-v3\_refreeze.py` |
| SHA256 | `DBEED815B895FC2A6D723BB5DB5274982782231224DD93C4CC795D98B0AB7FE7` |
| Invoked in v3 | **UNKNOWN** — no truthful invocation receipt exists; absence of a receipt is not a verified negative |
| Invoked in v4 | **UNKNOWN** — not copied into v4; no invocation receipt; not a verified “false” |
| Invoked in v5 | **UNKNOWN** — not copied into v5; not run; no live custody probe |

## Known vs UNKNOWN authoring actions
### Known (this v5 packet)
- UTF-8 file writes of four-role fake framing materials under Jim.
- `Get-FileHash` / content hashing for tip materials (no Python import/compile of prep helpers).
- Fresh copy of v4 tree into v5 host path, then selective edits for P1–P6.
- No Slack tip from Justin (Jim tips after verify).

### UNKNOWN
- Exact command that wrote v1 pyc `72615E8E…` (stated `-B` command insufficient).
- Whether `_refreeze.py` was ever invoked in v3/v4/v5 (no receipt → UNKNOWN, not verified false).
- Runtime behavior of v5 checker/invoke/admit/wrapper (held; not executed).

### Explicitly not done in v5
- **No** import/compile/invoke of prep helpers (`_prep_build_only`, `_refreeze`, or newly authored helpers).
- **No** checker / invoke / admit / wrapper / Docker execution.
- **No** native re-impl; **no** endpoint binding.
- **No** new live custody probes; **no** rerun to reconstruct history.

## Approval vs peer-review pins
| Pin | SHA256 | Role |
| --- | --- | --- |
| Trish approval receipt | `5C0B0F0B4EE98981C5CF58534FA8EA159C24C6315FEA9C834FF36A93D3878FA7` | Hash of `Trish-Preparation-Approval.json` |
| Jim/Dex peer-review | `722E4FDFCD51CBB57C8ADB678B6AEE9F314D2437A182118DD3B0D4E092EA1B5F` | Scope/review pin — **not** the Trish approval receipt |
| Dex v4 frozen REVISE intake | `E4BD67FCA22AE775456A06DDCC5FA0279C13DDA703708F61D62F69E21C083BFD` | `V4-Frozen-Intake-and-Static-Reconciliation.json` |
| Dex provisional static review | `B8A4B3EA6EAD919670794D3C67C6CFF6BAD62384EE90CE6F676386ED03B19F22` | `V4-Provisional-Static-Review.md` (P1–P5) |
| Dex provisional launcher review | `00FF53C86C9CEC0354E2E2578E366BAABD6A711E4CE51272FBCC024780351D9F` | `V4-Provisional-Launcher-Review.md` (P6) |
| Superseded v4 tip | `A40F0DEA7A01AF9C2361E707F0BBFB081BCB1D2D195510BD96EE2E25C43A01A6` | Immutable |

## Runtime pins
- 19 files: reused T07 inventory (17) + `ssl.py` + `email/message.py` parser additions.
- Explicit limit: **not** complete Python runtime closure (DLLs, site-packages, unlisted stdlib remain outside).

## Holds
`launch_ready=false` · `executed_in_preparation=false` · `execution_authorized=false` · endpoint unbound
