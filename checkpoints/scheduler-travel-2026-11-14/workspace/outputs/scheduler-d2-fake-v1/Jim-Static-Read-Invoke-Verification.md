# Jim static read — Dex Invoke-Verification.ps1 (HELD; not invoked)

**Subject:** `C:/Users/trish/Documents/Codex/2026-10-15/trish-wants-to-improve-dex-s/outputs/scheduler-d2-fake-v1/Invoke-Verification.ps1`  
**Observed SHA256:** `B72C1CBCAC9229F47FBB5E7A88462BB3D0C02DC8FA6B3DE163EE8FFECB195CA7` (matches Dex tip)  
**Byte semantics:** UTF-8 LF (no CR observed)  
**Reviewer:** Jim (Justin seat) — independent STATIC read only  
**Date:** 2026-11-11  
**Authority:** same D2 fake verification-packet authoring assignment; Dex p1794422760  
**Companion packet:** final MS-context successor `post-native-d2-source-fake-prep-jim-v4-ms-context-2026-11-11` TIP `3FC58EF9A45A40C5147C26040B49896DE396531EE55FC0059BC3F034874A6064`

## Scope of this read
Control flow, path containment, duplicate-pin refusal, count consistency, and the Python call boundary. No mock test, import, compile, execution, parse-as-runtime, or edit of Dex's wrapper. `VERIFICATION-ADMISSION.json` is not present yet (expected); wrapper must not be run.

## Control flow (static)
1. Mandatory `-AdmissionSHA256` (64 hex) — no default.
2. Hash-compare `VERIFICATION-ADMISSION.json` in `` against the parameter **before** JSON parse consumption for schema; mismatch → STOP, no child.
3. Schema gate: `kind == scheduler-d2-one-shot-fake-verification-admission`.
4. Packet pins: count must be non-zero and equal `packet_file_pin_count`; each relative path resolved under `/packet`; hash-checked.
5. Runtime pins: count non-zero and equal `runtime_file_pin_count`; absolute rooted paths only; hash-checked before Python.
6. Interpreter path must appear in the reviewed runtime inventory set.
7. Refuse existing evidence under `packet/fake-only-d2-path-admission-verification/`: `FAKE-D2-RESULT.json`, `FAKE-D2-LAUNCH-RECEIPT.json`.
8. `Push-Location` verify root → invoke interpreter `-I -S -B admit_outer.py` once → non-zero exit throws STOP with preserve-evidence / no-retry; `Pop-Location` in `finally`.

## Path containment
- Packet targets: `GetFullPath(Join-Path packetRoot, relative_path)` must `StartsWith(packetPrefix)` (OrdinalIgnoreCase). Escapes outside `packet/` refuse before hash I/O on that pin's content check path... actually hash is after containment check — good order.
- Runtime pins require rooted absolute paths; no relative runtime pin accepted.
- No `-File` / scriptblock / extra cwd mutation beyond Push/Pop of the verify root.

## Duplicate pin refusal
- `HashSet` (OrdinalIgnoreCase) on full packet target paths — duplicate packet pin → STOP.
- Separate `HashSet` on full runtime paths — duplicate runtime pin → STOP.
- Interpreter membership checked via `seenRuntimePaths.Contains(pythonPath)`.

## Count consistency
- `packet_files.Count` must equal `packet_file_pin_count` (and > 0).
- `runtime_files.Count` must equal `runtime_file_pin_count` (and > 0).
- Empty inventory refuses.

## Call boundary
- Single child: reviewed interpreter with `-I -S -B` and sole argument `admit_outer.py` under the verify root.
- No retry, repair, fallback, install, cleanup beyond location pop.
- No pytest / compile flags / network flags / second Python entry.
- Admission file is a mandatory external reviewed pin; wrapper does not generate it.

## Static disposition
**NO BLOCKER** for held authoring/review purposes. Wrapper shape matches the described one-shot boundary.

## Explicit non-claims
- Did not run the wrapper or `admit_outer`.
- Did not validate a concrete `VERIFICATION-ADMISSION.json` (absent by design until final freeze admission generation).
- Did not re-pin v4 packet files into Dex's `packet/` tree (not present beside the wrapper yet).
- Execution remains held pending Trish exact-hash one-shot approval after Dex generates admission from final frozen packet.

## Untouched
- Dex `Invoke-Verification.ps1` bytes (no edit)
- Frozen v1–v4 tip packets
- Application source / diff pins
