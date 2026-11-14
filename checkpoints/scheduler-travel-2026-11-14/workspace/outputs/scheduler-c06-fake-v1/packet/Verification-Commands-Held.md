# Verification commands — HELD, not executed

Preparation card explicitly forbids invoking these. Recorded for Dex independent review only.

Working directory (when a later card authorizes fake-only verification):

`F:/DropFolder/pending/post-native-c06-runner-tls-prep-jim-v1-corrected5-2026-11-10/fake-only-c06-verification/`

### Exact enforcing invocation (noncircular outer admission)

Layer 1 — operator verifies OUTER-ADMISSION.json bytes before start:
  OUTER-ADMISSION.json SHA256 F9638C51B23D86B9CBC2D587002C676223134709CBEC45110B5D8E03FE89F5EF

Layer 2 — exact enforcing entry (admit_outer.py):
  "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe" -I -S -B admit_outer.py

admit_outer.py then verifies interpreter + subject pins from OUTER-ADMISSION.json
(admit_outer, launcher, check, EXPECTED-OUTPUT, INPUT-MANIFEST, PACKET-SHA256SUMS)
with empty/whitespace pins refused (no silent waive), then spawns the launcher.

Pinned interpreter:
  Path:    C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe
  SHA256:  5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC

Do **not** invoke ambient `python -I -S -B check_c06_runner_tls_fake.py` as the outer entry.

Expected under a later fake-only execution card: admit/launcher exit 0; `FAKE-C06-RESULT.json` status PASS, executed=true, source_hashes_verified=true, inventory_error=null; control_ids_in_order match EXPECTED-OUTPUT.json; launch receipt retained; no app imports; no real Popen/sockets/PKI.

Not authorized by this packet:
- native Docker / Commands.ps1
- certificate generation
- `bash -n` / shell syntax execution of `prepare-c06-runner-tls.sh`
- `launch_ready=true`
- tests against app/vendor modules
- mutation of tipped v1, tipped corrected1, tipped corrected2, tipped corrected3, tipped corrected4, blocked draft, fake 22 PASS, or corrected7
