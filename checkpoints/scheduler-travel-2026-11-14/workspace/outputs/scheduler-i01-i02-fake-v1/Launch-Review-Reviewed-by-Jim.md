# I01/I02 corrected7 fake verification — launch review

Status: PREPARED, NOT EXECUTED. Dex static review has no unresolved source findings in the reviewed corrected7 packet. Jim's handback reconciles the reported findings; final review of Dex's staged invocation is pending. Trish's explicit launch authorization is required.

## Exact invocation

From PowerShell:

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-i01-i02-fake-v1\Invoke-Verification.ps1'
```

The invocation first rechecks the pinned Python executable, frozen tip, raw manifests, OUTER admission and enforcing script, then every artifact/harness/payload manifest entry. It refuses paths outside the staged packet, mismatches and prior result/receipt files. It then invokes the pinned Python311 executable with `-I -S -B` and `admit_outer.py` exactly once. The outer admission starts the reviewed launcher; the launcher starts one check child. No retry or repair path is provided.

| Reviewed item | SHA256 |
|---|---|
| Invoke-Verification.ps1 | B7F236B2F9AC0A963BDE6860A16130A799DBE78B7ED8D457DD6E2D3C867E92D4 |
| packet/ARTIFACT-HASHES.txt (raw bytes) | 1545B0C27192650A5AE4BFD2A2AEEEEC0DCD1B6600E7D80EDE90792486245CA0 |
| Frozen TIP | 6D19C5963C3CF2F1FBADDAE64AE0BE039D32C2C419A4EDCAB940E6314EB5084E |
| OUTER-ADMISSION.json | AACAAD3DDCD439AE50D51314172333A8E989DEB3C3E3C1A5824939F5490BBCAC |
| Harness manifest | 7A87A4E1E06498B668B53BB1BF11872488BBF71B3892A0D2D6BA2A297D510ECA |
| Check script | B8542F0C336E593C780A0DC062C4AB26A78F2534B9DC3A68FE71D4424A89973E |
| Python311 executable | 5F7B89A612C9B8AF1D6456CDFCD1DBE5CA630849E79AEBCED9BEE9A6694952EC |

## Verification scope

One verification attempt evaluates the exact 22 declared controls against AST-extracted fixture helpers and fake dependencies. It covers failure/cleanup primary preservation, I02 admission/diagnostic/helper guards, UUID/order/count checks, gate idempotence, C09 evidence/cancellation and registered-module extraction setup. It is not native SQL, real provider transport, production HTTP/native integration or TLS timing proof.

Static evidence: all 10 artifact, 6 harness and 267 payload entries match; all six outer subject pins match. All 286 staged files match Jim's source. All 234 workspace files match native v9. The PowerShell invocation has zero static parser errors. No Python imports, test/check invocation, sockets, Docker, database or installation was performed in preparation.

## Runtime scope requiring explicit inclusion in authorization

Three sequential `asyncio.run` cycles use standard Windows Proactor event-loop wakeup socket pairs. Each loop uses two connected internal sockets; the loopback fallback can briefly hold a third listening socket during pair construction. Scope is internal/local wakeup only; no provider, DNS, proxy, application endpoint or database network operations. Socket inventory has not been executed; the reviewed standard-library construction/closure paths and bounds are source-supported. This disclosure is not existing socket authority. Scheduler endpoint stays unbound.

The check also creates bounded local fake-control threads and temporary receipt files, with normal fixture retirement, and writes its result and launch receipt inside the staged harness directory. No real credentials or provider requests are used.

## Limits and stop behavior

- Check-child wait: 30 seconds.
- One child kill/wait on timeout or capture interruption: 5 seconds.
- Two capture-reader joins: 5 seconds each.
- Child collection plus retirement accounting: up to45 seconds, excluding outer hash admission and other local file operations. It is not a hard wall-clock bound on every outer process or OS operation.
- During-read capture: 65,536 bytes each stdout/stderr; result file admission: 262,144 bytes. Overflow interrupts the child and stops; unknown/incomplete/error reader retirement blocks result admission/PASS.
- Any collection primary/error/interrupt, failure, mismatch, timeout or UNKNOWN stops. Later exit0 cannot erase a primary error. No retry, repair or native continuation.
- Exact check child PID, executable, argv and start timestamp are retained for an unconfirmed termination. No process enumeration or extra cleanup authority is added. Required state-changing failure cleanup would return to Trish.

Expected retained files: `packet/fake-only-behavioral-harness/FAKE-BEHAVIORAL-RESULT.json` and `FAKE-BEHAVIORAL-LAUNCH-RECEIPT.json`. Dex will verify exit, exact ordered inventory/outcomes, source provenance, termination/reader retirement and hashes before claiming a pass. Original drops, all failed evidence and native v9 are preserved.

All native launches, installation/build/deployment, real-provider access, real credentials, endpoint binding and household Preview/Apply/worker activation remain held. The full active integration goal remains incomplete after a fake pass.