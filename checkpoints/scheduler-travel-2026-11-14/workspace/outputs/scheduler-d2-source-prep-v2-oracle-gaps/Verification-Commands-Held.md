# Verification commands — HELD, not executed (D2 path-admission fake prep v2 oracle gaps)

Preparation card explicitly forbids invoking these. Recorded for Dex independent review only.
Diff SHA256 CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4.
Overlay SHA256 CA51E2D8F40073C260942B5AF634229D253D9E2AA77177C45471037ED3C59B4D.
Controls-Plan SHA256 5072CED783E3ACA08EC28E760D6581D3916F1E5175F3CF830ABD5412C0B845BB.
Candidate three-file resulting hashes already match A265F81F… / AECE1018… / 875FBF61… (do not re-apply).
Supersedes frozen v1 tip A91964DA… (v1 remains immutable). Closes Dex provisional oracle gaps p1794421374.
This packet adds NO execution authority. launch_ready=false. executed_in_preparation=false.
Every later run separately gated.

Working directory (when a later card authorizes fake-only verification):

F:/DropFolder/pending/post-native-d2-source-fake-prep-jim-v2-oracle-gaps-2026-11-11/fake-only-d2-path-admission-verification/

### Exact enforcing invocation (noncircular outer admission)

Layer 1 — operator verifies OUTER-ADMISSION.json bytes before start:
  OUTER-ADMISSION.json SHA256 A86238B606D370F28F679492BD46F69B005F7C4D5F3E5783A33FC53367A760B6

Layer 2 — exact enforcing entry (admit_outer.py):
  "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe" -I -S -B admit_outer.py

admit_outer.py then verifies interpreter + subject pins from OUTER-ADMISSION.json
(admit_outer, launcher, check, EXPECTED-OUTPUT, INPUT-MANIFEST, PACKET-SHA256SUMS)
with empty/whitespace pins refused (no silent waive), then spawns the launcher.

Pinned interpreter:
  Path:    C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe
  SHA256:  5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC

Pinned check (authored, not executed):
  check_d2_path_admission_fake.py SHA256 82017D3336FB8CD32336979C6ECA968FF5D442402A290EF14E8E1914F732D5A0

MANIFEST-SELF (INPUT-MANIFEST.json):
  5BFE0746D23A92604CBB11B1BEFD1FA95B1CD6F93347A34224D05490C5C6C495

Do **not** invoke ambient python -I -S -B check_d2_path_admission_fake.py as the outer entry.

### Held launcher limits (do not run in this card)
- One pinned Python invocation
- 30s child wait, 5s termination/wait, two 5s reader joins
- 64 KiB stdout/stderr each, 256 KiB result
- Reuse T02 admit_outer / invoke structure with new D2 pins/labels; no old T02 evidence reuse

Expected under a later fake-only execution card: admit/launcher exit 0; FAKE-D2-RESULT.json status PASS, class FAKE-D2-PATH-ADMISSION, executed=true, source_hashes_verified=true, inventory_error=null; control_ids_in_order match EXPECTED-OUTPUT.json (52 named controls = 44 functional [41 approved core + 3 CTX oracle-gap additions] + 3 mutations + 5 inventory self-checks, exact emitted order); launch receipt retained; no app imports; no real sockets/PKI/providers/credentials.

NOT-AUTHORIZED by this packet:
- execution of admit_outer / invoke / check
- tests / imports of app
- code compilation beyond later authorized harness
- certificate generation / real TLS
- Docker / native continuation
- endpoint binding / profile binding
- launch_ready=true
- mutation of original T02 trees, native trees, frozen v1 tip, or the three already-applied candidate source files
- claiming full provider transport proof or closing T01–T08
