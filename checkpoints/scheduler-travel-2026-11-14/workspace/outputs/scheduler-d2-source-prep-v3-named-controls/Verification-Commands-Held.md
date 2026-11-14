# Verification commands — HELD, not executed (D2 path-admission fake prep v3 named controls)

Preparation card explicitly forbids invoking these. Recorded for Dex independent review only.
Diff SHA256 CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4.
Overlay SHA256 CA51E2D8F40073C260942B5AF634229D253D9E2AA77177C45471037ED3C59B4D.
Controls-Plan SHA256 5072CED783E3ACA08EC28E760D6581D3916F1E5175F3CF830ABD5412C0B845BB.
Candidate three-file resulting hashes already match A265F81F… / AECE1018… / 875FBF61… (do not re-apply).
Supersedes frozen v2 tip 9794FE5B… (v2 remains immutable). Incorporates Dex formal REVISE (oracle gaps from v2) + named-control findings p1794422024.
Predecessor frozen v1 tip A91964DA… also remains immutable.
This packet adds NO execution authority. launch_ready=false. executed_in_preparation=false.
Every later run separately gated.

Working directory (when a later card authorizes fake-only verification):

F:/DropFolder/pending/post-native-d2-source-fake-prep-jim-v3-named-controls-2026-11-11/fake-only-d2-path-admission-verification/

### Exact enforcing invocation (noncircular outer admission)

Layer 1 — operator verifies OUTER-ADMISSION.json bytes before start:
  OUTER-ADMISSION.json SHA256 D330D9BAE50BE9589A675FAA95EE618828288FE78704CB25BF84B65FD14669D2

Layer 2 — exact enforcing entry (admit_outer.py):
  "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe" -I -S -B admit_outer.py

admit_outer.py then verifies interpreter + subject pins from OUTER-ADMISSION.json
(admit_outer, launcher, check, EXPECTED-OUTPUT, INPUT-MANIFEST, PACKET-SHA256SUMS)
with empty/whitespace pins refused (no silent waive), then spawns the launcher.

Pinned interpreter:
  Path:    C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe
  SHA256:  5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC

Pinned check (authored, not executed):
  check_d2_path_admission_fake.py SHA256 A8787F873BC54BFE1B71BB487716DF14D85D21BB932B5EE53BCA0A5F1AB9C9FC

EXPECTED-OUTPUT.json SHA256 1ACD3F2D0F223C9C637C6F1EAE526E675A6D8618AF87ACDADD923EBF77AA5667

MANIFEST-SELF (INPUT-MANIFEST.json):
  8C772F15EA8065A718E8262786020CADF0B2C5E53F3D3AE5404B9499D5AC14F7

Do **not** invoke ambient python -I -S -B check_d2_path_admission_fake.py as the outer entry.

### Held launcher limits (do not run in this card)
- One pinned Python invocation
- 30s child wait; 5s post-kill wait; two 5s reader joins
- 64 KiB stdout/stderr each; 256 KiB result capture
- No app package imports, sockets, PKI, Docker, native, endpoint bind
