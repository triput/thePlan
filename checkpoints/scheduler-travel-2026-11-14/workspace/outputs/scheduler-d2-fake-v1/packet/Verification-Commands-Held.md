# Verification commands — HELD, not executed (D2 path-admission fake prep v4 MS context)

Preparation card explicitly forbids invoking these. Recorded for Dex independent review only.
Diff SHA256 CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4.
Overlay SHA256 CA51E2D8F40073C260942B5AF634229D253D9E2AA77177C45471037ED3C59B4D.
Controls-Plan SHA256 5072CED783E3ACA08EC28E760D6581D3916F1E5175F3CF830ABD5412C0B845BB.
Candidate three-file resulting hashes already match A265F81F… / AECE1018… / 875FBF61… (do not re-apply).
Supersedes frozen v3 tip A9415BB7… (v3 remains immutable). Check-only: MS VIEW/DELTA via run_client_get context/client → CoveringHTTP (p1794422580).
Predecessor frozen v1 tip A91964DA… and v2 tip 9794FE5B… also remain immutable.
This packet adds NO execution authority. launch_ready=false. executed_in_preparation=false.
Every later run separately gated.

Working directory (when a later card authorizes fake-only verification):

F:/DropFolder/pending/post-native-d2-source-fake-prep-jim-v4-ms-context-2026-11-11/fake-only-d2-path-admission-verification/

### Exact enforcing invocation (noncircular outer admission)

Layer 1 — operator verifies OUTER-ADMISSION.json bytes before start:
  OUTER-ADMISSION.json SHA256 B8D14DAB5127362165E7D87B4BBFA32DC9EAC7175A621C97EB97B69F0457354D

Layer 2 — exact enforcing entry (admit_outer.py):
  "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe" -I -S -B admit_outer.py

admit_outer.py then verifies interpreter + subject pins from OUTER-ADMISSION.json
(admit_outer, launcher, check, EXPECTED-OUTPUT, INPUT-MANIFEST, PACKET-SHA256SUMS)
with empty/whitespace pins refused (no silent waive), then spawns the launcher.

Pinned interpreter:
  Path:    C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe
  SHA256:  5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC

Pinned check (authored, not executed):
  check_d2_path_admission_fake.py SHA256 CAAECE741F12F632FFC97207D47BEA6340EBFD62CB20AE86EE84C389BD73C4CB

EXPECTED-OUTPUT.json SHA256 381536B156A37EE5C3F7A1FABBC0F0C2942FE97BBC68B68F67550BF715C368FC

MANIFEST-SELF (INPUT-MANIFEST.json):
  4E2AC286F3B9CA3DF888E4C6C2A2C40DBF092E38819F27A7EE1B0314E7F2E02D

Do **not** invoke ambient python -I -S -B check_d2_path_admission_fake.py as the outer entry.

### Held launcher limits (do not run in this card)
- One pinned Python invocation
- 30s child wait; 5s post-kill wait; two 5s reader joins
- 64 KiB stdout/stderr each; 256 KiB result capture
- No app package imports, sockets, PKI, Docker, native, endpoint bind
