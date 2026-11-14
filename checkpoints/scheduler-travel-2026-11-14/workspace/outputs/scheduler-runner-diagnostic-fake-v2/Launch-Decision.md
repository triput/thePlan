# Runner-diagnostic fake verification v2: preparation (HELD)

Matt, November 12, 2026, for Dex review. Assignment: `Matt-thePlan-Scheduler-Diagnostic-Fake-V2-Preparation-2026-11-12.md` (`7BC58DDF…49EF`). Trish's approval receipt: `scheduler-runner-diagnostic-fake-v1.evidence/Fresh-Copy-Preparation-Approval.json`.

**No execution is authorized.** Nothing here has been imported, parsed, compiled, tested or invoked. Both `launch_authorized` booleans are false, and no EXECUTE acknowledgement exists. **No PASS is claimed**: the authored syntax and behavior remain unverified.

## What changed from v1
- **Baseline:** a fresh copy of `scheduler-native-provider-runner-diagnostic-fake-prep-matt-v1`. Its 14 input pins (manifest `398F8A3C…CA3D`) all verified before copying. v1, the failed staging copy `scheduler-runner-diagnostic-fake-v1` and its `.evidence` are untouched. No result or receipt was copied, and none exists here.
- **The only executable-byte change** is the approved diff `41E0506D…01F0` to `packet/verify/check_native_provider.py`, line 872 (`fallback_mutant` anchor), applied with `patch -p1`:
  - `-                      ("return original  # Diagnostic failure must not replace the primary kind.", "raise"))`
  - `+                      ("return original", "raise"))`
  - The checker hash goes from `D4010F1B…EBE8` to **`BA1C333D5109D38569B6784332B1291B1035EF88737D774D303F34F88D6C4C7A`**, the expected exact candidate. It is LF only, with indentation and encoding preserved.
- **Data and label refresh:**
  - `OUTER-ADMISSION.json` now carries the checker pin, the packet label `…-v2` and its note. New hash `22257FDEE02FD88893F2D1B5C5CC79F8DCD2205090C1B192D1DFEB9F47074723`.
  - `VERIFICATION-ADMISSION.json` now carries the checker pin, the OUTER pin, the packet label `…-v2` and its note. New hash `DD9FB1BDD48077A5CD053930AA0A50B49026B9731C2B456D370D5BECDBA3D99C`.
  - This document and `Future-Command-HELD.ps1.txt` were rewritten for v2. The v1 versions stay only in the v1 folder; no historical v1 command or decision text is kept here.
- **Intentionally byte-identical, per the assignment:**
  - all 14 controls and assertions, the expected `FileNotFoundError` oracle, the replacement `raise` and the unique-anchor guard;
  - all subject bytes;
  - `EXPECTED-FAKE-STRUCTURAL.json` (`D6702FE7…EE32`);
  - wrapper `Invoke-Fake.ps1` (`AE84E632…FEB7`), launcher (`D22C37E3…BD07`) and outer admission script (`7DCA32E2…18FB`).
- **Retained v1 lineage labels:** the checker's `PACKET_NAME` and EXPECTED's `"packet"` still read `…-fake-prep-matt-v1`. That's deliberate: changing them would widen the one-line diff. So a v2 result file will report `packet: …-fake-prep-matt-v1`. The admissions, this document and the input manifest identify the actual v2 packet.

## Inventories
**Packet pins in VERIFICATION (11):**

| File | SHA256 |
| --- | --- |
| `verify/check_native_provider.py` | `BA1C333D…4C7A` |
| `verify/launch_check.py` | `D22C37E3…BD07` |
| `verify/verify_admission.py` | `7DCA32E2…18FB` |
| `verify/EXPECTED-FAKE-STRUCTURAL.json` | `D6702FE7…EE32` |
| `verify/OUTER-ADMISSION.json` | `22257FDE…4723` |
| `Invoke-Fake.ps1` | `AE84E632…FEB7` |
| `subjects/original/np_runner_entry.py` | `7FBDCAEE…5FF5` |
| `subjects/candidate/np_runner_entry.py` | `40A1BA8E…F73F` |
| `subjects/host/docker_transport.py` | `7F7EA820…AC53` |
| `subjects/producer/runner_entry.py` | `2A4602CC…FA3E` |
| `subjects/diff/V3-Proposed-Runner-Diagnostic.diff` | `F6135717…9832` |

**Runtime pin (1, interpreter only):** `C:\Users\trish\AppData\Local\Programs\Python\Python311\python.exe` `5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC`. This is not a standard-library, DLL or environment lock.

**Acyclic chain:** the wrapper takes the VERIFICATION hash as an argument; VERIFICATION pins OUTER and the other 10 packet files; OUTER pins the checker, launcher, EXPECTED and interpreter. Nothing pins back up the chain.

`Input-Manifest.sha256` covers every file in this packet except itself (14 entries).

## Limits (unchanged from v1)
- **Timing:** checker budget 120 s, plus at most one 5 s kill/wait of the single owned child, plus two 5 s capture-reader joins: **135 s nominal**. Startup, process and thread construction, hashing, file and receipt I/O, and OS latency are excluded. There is no separate outer timeout, and a tool-observation timeout is not authority to restart.
- **Capture:** 64 KiB each for stdout and stderr; 256 KiB for the result.
- **Success** requires exit 0, zero stdout and stderr output, joined clean EOF readers with no reader error or overflow, and the exact ordered 14-control PASS inventory.
- **Exclusive fresh evidence paths:** `packet/verify/FAKE-NATIVE-PROVIDER-RESULT.json` and `packet/verify/FAKE-NATIVE-PROVIDER-LAUNCH-RECEIPT.json`, both absent now. Existing evidence refuses admission.
- **On any failure, timeout, mismatch or UNKNOWN:** stop and preserve evidence; no retry, repair, rerun or cleanup.
- **Scope:** fake behavior of the extracted blocks only. No native, PKI, TLS, Docker, database or provider proof, and no v3 raise-site attribution.
- **Never executed:** the `context_ignored` and `walk_129` mutant oracles. The v1 run's progress through controls 1–13 is an ordering inference only.

## Future command
`Future-Command-HELD.ps1.txt`, the absolute path to this packet's wrapper with admission `DD9FB1BD…D99C`. Against this prep admission the wrapper refuses before starting any child. A run needs:
- a reviewed staging change that flips both booleans;
- the resulting new admission hash;
- Trish's explicit one-shot approval, including authority to terminate the one owned check child on error, timeout or overflow.
