# Jim-Static-Read — Invoke-Verification.ps1 (T07)

Static review only. NOT invoked. NOT edited.

## Pin
- Path: `C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-t07-fake-v1/Invoke-Verification.ps1`
- SHA256: `1DEA20EC5AC6C475EEEEC22EEE9B38381F31EA319B7A059409BC2BE52CE9D16B` (re-verified)
- Compared to D2 wrapper SHA256 `B72C1CBCAC9229F47FBB5E7A88462BB3D0C02DC8FA6B3DE163EE8FFECB195CA7`

## Diff vs D2 (only admission-kind / folder / FAKE-T07 output-name substitutions)
1. `$admission.kind` expect `scheduler-t07-one-shot-fake-verification-admission` (was `scheduler-d2-...`)
2. `$verifyRoot` → `packet/fake-only-t07-retirement-verification` (was `fake-only-d2-path-admission-verification`)
3. Pre-existing evidence refuse names → `FAKE-T07-RESULT.json`, `FAKE-T07-LAUNCH-RECEIPT.json` (was FAKE-D2-*)

No other structural deltas observed in unified diff.

## Containment / count / duplicate gates (present)
- Mandatory 64-hex `$AdmissionSHA256`; live `VERIFICATION-ADMISSION.json` hash must match before any child.
- Admission JSON `kind` schema gate.
- Packet pins: count must equal `packet_file_pin_count`; each `relative_path` + 64-hex sha; fullpath must stay under `$packetRoot` prefix; HashSet rejects duplicates; live file hash must match pin.
- Runtime pins: count must equal `runtime_file_pin_count`; absolute rooted paths; HashSet rejects duplicates; live hash match.
- Interpreter path must appear in reviewed runtime inventory before start.
- Refuse if FAKE-T07 result/receipt already exist (no replay/overwrite).

## Single Python boundary
- Exactly one Python spawn: `python -I -S -B admit_outer.py` under `$verifyRoot`.
- Non-zero exit → STOP; preserve evidence; no retry/repair.
- No tests, installs, fallback, or extra cleanup in the wrapper.

## Disposition
**NO BLOCKER** — wrapper is the reviewed D2 one-shot pattern with T07 label/path substitutions only; gates intact for a later exact-hash card. This preparation does not authorize invoke.
