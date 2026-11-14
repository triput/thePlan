# Verification commands — HELD, not executed (T07 retirement fake prep v1)

Preparation card explicitly forbids invoking these. Recorded for Dex independent review only.
Diff SHA256 8623F550F8B0BE9DFA00EBD8AD066768F22BE0750DC3DD635CF0A2F7A4CE7808.
Design TIP v3 SHA256 94362F46EE6912A9A6F2A7CB64A673E51A2037D145A1FB70721F373FE2B7AA91.
Scope SHA256 B1481463CA6993C6C4C884485237E5DD2C308B7578A796DE5DE89565BDD46C83.
Candidate three-file resulting hashes match E942BB43… / 2E6A4ABB… / 84F50367….
This packet adds NO execution authority. launch_ready=false. executed_in_preparation=false.
D2 one-shot not launched. Every later run separately gated.

Working directory (when a later card authorizes fake-only verification):

F:/DropFolder/pending/post-native-t07-source-fake-prep-jim-v1-2026-11-11/fake-only-t07-retirement-verification/

### Exact enforcing invocation (noncircular outer admission)

Layer 1 — operator verifies OUTER-ADMISSION.json bytes before start:
  OUTER-ADMISSION.json SHA256 7559C27C361FE8A50A89C98DC412D2741342786C5AE1880D22531A17885B369D

Layer 2 — exact enforcing entry (admit_outer.py):
  "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe" -I -S -B admit_outer.py

admit_outer.py then verifies interpreter + subject pins from OUTER-ADMISSION.json
(admit_outer, launcher, check, EXPECTED-OUTPUT, INPUT-MANIFEST, PACKET-SHA256SUMS)
with empty/whitespace pins refused (no silent waive), then spawns the launcher.

Pinned interpreter:
  Path:    C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe
  SHA256:  5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC

Pinned check (authored, not executed):
  check_t07_retirement_fake.py SHA256 E6C55113DE49D83183BCA14F4113CB0B38566D85839AB5B39BAF63C986007E7F

EXPECTED-OUTPUT.json SHA256 56F576375D1F96907FE9127040AB258FA2B6D0D61FB719579732CB94BAEE9FF8

MANIFEST-SELF (INPUT-MANIFEST.json):
  538888433F9D0BA3CFE302D10891D52360EE5577B88E353EA29256C0CD74D0A1

Do **not** invoke ambient python -I -S -B check_t07_retirement_fake.py as the outer entry.

### Held launcher limits (do not run in this card)
- One pinned Python invocation
- 30s child wait; 5s post-kill wait; two 5s reader joins
- 64 KiB stdout/stderr each; 256 KiB result capture
- No app package imports, sockets, PKI, Docker, native, endpoint bind
