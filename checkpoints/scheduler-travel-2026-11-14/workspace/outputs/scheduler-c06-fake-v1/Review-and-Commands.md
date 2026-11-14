# Corrected5 fake-only verification — launch review, HELD

Jim's frozen corrected5 TIP5F8D87526F9D2C114C2B81A0D06D3ED2A5CEBC7E2DC97A562225C9C2FB23C602 is independently reconciled. All20 artifact,268 payload and6 verification manifest entries match. All284 staged files match the original bytes. Only runner_entry.py and its payload-manifest entry changed from corrected4; the exact unified diff reconstructs the new runner hash2A4602CCDFA68787697ED4FD472B3BEA41FD9FC31F8F808C409339140C81FA3E. Other fixture sources, production/host code and prior evidence are preserved.

Static disposition: ready for Trish's separate fake-only execution decision; no unresolved blocker found in the reviewed scope. No import, compilation, test or launch performed. This is not PKI, real process-group behavior or native lost-ack proof.

The39 authored controls exercise extracted fixture functions using in-memory processes, pipes, filesystems, TLS contexts and fake Linux signal/path semantics. Explicit static inventory controls remain static. Source extraction registers modules before exec into coherent globals, requires symbols and admits four fixture sources plus the consumed launch configuration. The new partial-construction control expects two pipe close attempts, one constructed/zero started readers, preserved primary and STOP. Actual expected case order/outcomes live in the staged EXPECTED-OUTPUT.json; they are not passing results yet.

Exact held invocation from this workspace:

& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-c06-fake-v1\Invoke-Verification.ps1'

Invoke-Verification.ps1 SHA256: 1B912ECED717BB7F83E9AE09D103A940EBC9D68D6D089DFE1B7121252DB943F5
Outer admission SHA256: F9638C51B23D86B9CBC2D587002C676223134709CBEC45110B5D8E03FE89F5EF
Raw verification INPUT-MANIFEST.json SHA256: F0DFF3AC396AC11B6A6A7ADB6F3E367CA28956871AE6E861E28FCEB0475CC26E

Process scope: PowerShell admission invokes pinned Python311 outer admission with -I -S -B. That outer entry spawns a real local Python launcher, which starts one real Python check child and two capture-reader threads. Processes within the extracted fixture are fake; no real OpenSSL, process groups, TLS sockets, provider/network/database/app/vendor imports, Docker or installation are included.

Limits: check child wait30s; one kill/wait up to5s on timeout/error; two reader joins up to5s each, for45s disclosed collection/retirement. This excludes outer hash admission, file operations and process-start/OS latency; no total hard wall-clock bound is claimed. Captures64KiB each stdout/stderr; result256KiB. Retain output/result and launch receipt. Unconfirmed child/reader retirement, failure, mismatch, timeout or unexpected output stops with no retry/repair/continuation. No extra cleanup or native launch is authorized.

The wrapper refuses pre-existing result/receipt before launch to preserve one-shot evidence. Original packets remain untouched; authorized outputs would be written only in the fresh workspace packet. Endpoint remains unbound; every other hold stays. The full HTTP/native, actual contention and all T01–T08 proof obligations remain open.