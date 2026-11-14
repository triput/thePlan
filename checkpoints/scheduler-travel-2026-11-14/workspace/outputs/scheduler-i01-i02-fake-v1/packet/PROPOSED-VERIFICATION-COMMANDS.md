# PROPOSED-VERIFICATION-COMMANDS.md — REVISE2-corrected7
# NOT EXECUTED during preparation. Exact proposed commands + hashes.

## Fake-only behavioral (separate packet; outside native payload)

Working directory:
  F:/DropFolder/pending/post-native-I01-I02-fixture-prep-jim-v1-REVISE2-corrected7-2026-11-10/fake-only-behavioral-harness

### Exact enforcing invocation (noncircular outer admission)

  Layer 1 — operator verifies OUTER-ADMISSION.json bytes before start:
    OUTER-ADMISSION.json SHA256 AACAAD3DDCD439AE50D51314172333A8E989DEB3C3E3C1A5824939F5490BBCAC

  Layer 2 — exact enforcing entry (admit_outer.py):
    "C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe" -I -S -B admit_outer.py

  admit_outer.py then verifies interpreter + subject pins from OUTER-ADMISSION.json
  (admit_outer, launcher, check, EXPECTED-OUTPUT, INPUT-MANIFEST, PACKET-SHA256SUMS)
  with empty/whitespace pins refused (no silent waive), then spawns the launcher.

### Pinned interpreter (exact)

  Path:    C:/Users/trish/AppData/Local/Programs/Python/Python311/python.exe
  Version: 3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
  SHA256:  5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC
  Enforced by: admit_outer (OUTER-ADMISSION) AND launcher pre-admission (hardcoded pin)

### Pinned inputs

  OUTER-ADMISSION.json               SHA256 AACAAD3DDCD439AE50D51314172333A8E989DEB3C3E3C1A5824939F5490BBCAC
  admit_outer.py                     SHA256 A5BC16C076AA3CB9BD4B8E36C3895FEFF58E028DEE28532B1CCBD90A25E8A97B
  INPUT-MANIFEST.json                SHA256 91F29BA6A7A5531A4528508B9E668E3CADFADEB796C73416DB561EBB08CCD617
  EXPECTED-OUTPUT.json               SHA256 BF179EA6657391E3DFBFCC5AF7F9D0ED1D42E884DA712C625D95563C1666DB6A
  check_i01_i02_fake_behavioral.py   SHA256 B8542F0C336E593C780A0DC062C4AB26A78F2534B9DC3A68FE71D4424A89973E
  invoke_fake_behavioral.py          SHA256 B03C3458A453F863DD6AB7C6E21E56800A84F8E4B763582BC441B59D9BFA48F6
  PACKET-SHA256SUMS.txt              SHA256 7A87A4E1E06498B668B53BB1BF11872488BBF71B3892A0D2D6BA2A297D510ECA
  REVIEW.md                          SHA256 D2060EBEB8B137996F3476FFCE10AD6B09DCA0FD4E909F50B84BAC8628553530

### Pin layers (identify each)

  1. Outer reviewed file: OUTER-ADMISSION.json (operator-compared hash above; file does not embed its own hash)
  2. Outer admit: admit_outer.py — enforces layer-1 subject pins, then spawns launcher
  3. Launcher: invoke_fake_behavioral.py — interpreter hardcoded pin; check/EXPECTED/INPUT-MANIFEST vs PACKET-SHA256SUMS (launcher does NOT self-compare its own final raw-byte hash); isolation; bounded capture-during-collection with reader retirement accounting + overflow interrupt + collection-interrupt exit confirmation; primary collection/wait error or unexpected interrupt blocks result admission/PASS even after confirmed exit 0; child_pid custody pinned at Popen success (executable/argv/start timestamp; receipt-only); ordered result gate
  4. Check script: fixture source SHA vs INPUT-MANIFEST; exact EXPECTED inventory + ordered emission contract; N14 method `__globals__` patch visibility; Choice B Windows asyncio internal socket disclosure

### Bounded contract (enforced; not left to unspecified caller)

  - Isolation: outer/parent/child require `-I -S -B`; `-I`→`sys.flags.isolated`, `-S`→`sys.flags.no_site` (not merely `no_user_site`), `-B`→`dont_write_bytecode`
  - Capture admission: bounded pipe readers during collection (chunked); over-limit → interrupt child + STOP; still-live/incomplete/error reader → UNKNOWN (blocks PASS + result validation); process exit alone does not imply reader EOF; timeout kill/wait exceptions retained as secondary evidence; any collection interrupt/error (incl. proc_wait_error with capture_stop=None) requires explicit non-None child-exit confirmation before result validation or child_exited_normally (pe primary; no retry); **any primary collection/wait error or unexpected collection interrupt prevents result admission/PASS even when child exit later proves 0** (retaining primary_error on PASS is not stop-on-failure); disclosed timeout_retirement_limits (30 + 5 + 2×5 = **45s** total; no retry); this is child/retirement accounting only — distinct from any outer-admission deadline; retained-tail clip alone ≠ capture limit; result `read_bytes` only after size gate
  - child_pid custody: pin `proc.pid` as soon as Popen succeeds, plus executable/argv and creation/start timestamp on receipt for read-only reconciliation if termination unconfirmed; no process enumeration, retry, fallback, or new cleanup authority
  - Result gate: refuse stale / missing / malformed / non-PASS; require exact expected control IDs+order (`control_ids_in_order` == controls key order == EXPECTED order), every expected result, `inventory_error=None`, `source_hashes_verified=True`, `executed=True`; exit0 alone cannot PASS
  - Windows asyncio internal sockets (Choice B / Dex p1794366344): N11 three sequential `asyncio.run` use WindowsProactorEventLoopPolicy; BaseProactorEventLoop self-pipe via `socket.socketpair` (or loopback bind/listen/connect/accept fallback); concurrent bound 2 connected sockets per live loop; sequential 3 create/retire cycles; loopback-only; retired on `loop.close`; NOT provider/DNS/proxy/app/database; no socket inventory executed; no socket authority added; packet must not claim literally no sockets
  - Synthetic module setup covered by N14 / P_synthetic_module_registration (`SharedTransportScript.take.__globals__`)
  - Retained receipt: FAKE-BEHAVIORAL-LAUNCH-RECEIPT.json
  - Check output: FAKE-BEHAVIORAL-RESULT.json
  - Exit codes: 0 PASS / 1 FAIL / 124 timeout / 125 STOP|UNKNOWN
  - stdlib + fake seams only; no app/vendor imports, Docker, provider/DNS/proxy/app network, DB
  - no retries / no automatic repair

## Native / integrated (later card; unbound)

  NOT authorized by this preparation packet.
  Endpoint remains unbound.
  Fake PASS cannot waive native SQL contention, TLS terminal, or integrated timing.

## Fixture-Changes.diff

  Primary baseline: tipped REVISE2-corrected6 parent (preserved).
  SHA256 96872AB529E219A121CA6BB204DF448AF5F2847D9AD49B7C72EE2ED1E2D5B585
