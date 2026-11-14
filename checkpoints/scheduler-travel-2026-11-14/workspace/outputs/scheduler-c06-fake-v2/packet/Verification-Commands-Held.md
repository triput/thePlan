# Verification commands — HELD, not executed

Preparation card explicitly forbids invoking these. Recorded for Dex independent review only.

Working directory (when a later card authorizes fake-only verification):

`F:/DropFolder/pending/post-native-c06-runner-tls-prep-jim-v1-corrected6-2026-11-10/fake-only-c06-verification/`

### Exact enforcing invocation (noncircular outer admission)

Layer 1 — operator verifies OUTER-ADMISSION.json bytes before start:
  OUTER-ADMISSION.json SHA256 C9A0B5214F752F2FFED9ACE3E983501F44B4D78FA6D030774ABC61DDFBC212BF

Layer 2 — exact enforcing entry (admit_outer.py):
  "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe" -I -S -B admit_outer.py

admit_outer.py then verifies interpreter + subject pins from OUTER-ADMISSION.json
(admit_outer, launcher, check, EXPECTED-OUTPUT, INPUT-MANIFEST, PACKET-SHA256SUMS)
with empty/whitespace pins refused (no silent waive), then spawns the launcher.

Pinned interpreter:
  Path:    C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe
  SHA256:  5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC

Pinned check (corrected6 fresh-copy one-line fix; parent corrected5 check retained on tipped parent):
  check_c06_runner_tls_fake.py SHA256 C59C547453A76ACF7C4F10B8A0E1576134AB24A978EE5CC8018D25E1EF775DF8
  parent corrected5 check SHA256 99C3049C69C5837C728236D6ED8332A286A0E22FF6A35A8C47157165CF78D51E
  Proposed-Fix.diff SHA256 2F798B6F1F4B0C968A198746F36FF55D9776935B678A6DA6F08962D563D23F47
  Fresh-Preparation-Approval call_32f9e623299f4b0e8bc3eed4532b8278

Do **not** invoke ambient `python -I -S -B check_c06_runner_tls_fake.py` as the outer entry.

Expected under a later fake-only execution card: admit/launcher exit 0; `FAKE-C06-RESULT.json` status PASS, executed=true, source_hashes_verified=true, inventory_error=null; control_ids_in_order match EXPECTED-OUTPUT.json; launch receipt retained; no app imports; no real Popen/sockets/PKI.

Not authorized by this packet:
- native Docker / Commands.ps1
- certificate generation
- `bash -n` / shell syntax execution of `prepare-c06-runner-tls.sh`
- `launch_ready=true`
- tests against app/vendor modules
- mutation of tipped corrected5, tipped v1, tipped corrected1, tipped corrected2, tipped corrected3, tipped corrected4, blocked draft, fake 22 PASS, corrected7, or failed workspace scheduler-c06-fake-v1
