# T05 fake framing prep v4 — authoring custody

## Immutable predecessors
- v1 / v2 / v3 prep packets untouched.
- Dex `native-dex-*` dirs untouched; B8 deferred to Dex.

## v1 helper compile receipt (preserved; do not delete/run)
| Field | Value |
| --- | --- |
| Path | `C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-t05-original-framing-prep-v1\__pycache__\_prep_build_only.cpython-311.pyc` |
| SHA256 | `72615E8E4EABB57A9032EF695B2752139E1BCFE42759560A4C71AB5E35AE12CC` |
| Bytes | 29470 |
| mtime UTC | 2026-11-11T21:54:19.0696255Z |
| Authoring commands (v1 one-shot) | `python -I -S -B _prep_build_only.py` (source since removed; pyc retained); implicit compile produced the pyc during that authoring pass only |
| Meaning | Helper compilation for wire/manifest **authoring** in v1 — **not** checker/invoke/admit/wrapper/Docker execution |

## `_refreeze.py`
| Field | Value |
| --- | --- |
| Observed on v3 | `...\scheduler-t05-original-framing-prep-v3\_refreeze.py` |
| SHA256 | `DBEED815B895FC2A6D723BB5DB5274982782231224DD93C4CC795D98B0AB7FE7` |
| Invoked in v3 | **false** (no truthful receipt of invocation) |
| Invoked in v4 | **false** — not copied into v4; not run |

## v4 authoring hold (this packet)
- **No** import/compile/invoke of prep helpers (`_prep_build_only`, `_refreeze`, or newly authored helpers).
- **No** checker / invoke / admit / wrapper / Docker execution.
- Authoring performed via UTF-8 file writes + `Get-FileHash` only.
- Evidence-based distinction: v1 one-shot helper compile occurred and is preserved; v4 preparation stayed on the no-import/no-compile hold.

## Approval vs peer-review pins
| Pin | SHA256 | Role |
| --- | --- | --- |
| Trish approval receipt | `5C0B0F0B4EE98981C5CF58534FA8EA159C24C6315FEA9C834FF36A93D3878FA7` | Hash of `Trish-Preparation-Approval.json` |
| Jim/Dex peer-review | `722E4FDFCD51CBB57C8ADB678B6AEE9F314D2437A182118DD3B0D4E092EA1B5F` | Scope/review pin — **not** the Trish approval receipt |

## Runtime pins
- 19 files: reused T07 inventory (17) + `ssl.py` + `email/message.py` parser additions.
- Explicit limit: **not** complete Python runtime closure (DLLs, site-packages, unlisted stdlib remain outside).

## Holds
`launch_ready=false` · `executed_in_preparation=false` · `execution_authorized=false` · endpoint unbound
