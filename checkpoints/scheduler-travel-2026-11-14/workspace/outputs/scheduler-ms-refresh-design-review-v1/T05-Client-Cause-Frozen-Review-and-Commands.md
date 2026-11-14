# T05 client-cause diagnostic — reviewed fake verification v1

Dex, 2026-11-13. Qualified static acceptance; no remaining static blocker found for this finite scope. Syntax and behavior remain unexecuted. Native T05 remains held.

Matt handback 99A5D4253911DC524AA8D5A4AF435D7281A1347EA2C63AE4136D6C4B0580F357 and all 26 sidecar pins match. All 301 native-preparation inputs, 20 fake-preparation inputs, 17 contained fake packet pins and 10 partial runtime pins match. Failed source 297 inputs, retained failed receipt A80D7DF9 and 234 application files independently checked unchanged. Runner text diff is exactly the new helper, caught client object retention and replacement call after retirement/inventory. Classifier, producer, peer, host validator and actual assertions preserved.

Fresh staging: outputs/scheduler-native-t05-client-cause-fake-dex-v1. Eighteen of twenty copied inputs remain byte-identical. Only OUTER and VERIFICATION admission metadata change to stage a future authorized invocation; executable/checker/subject/EXPECTED bytes unchanged. Those flags do not authorize execution. Copied preparation command and Launch-Decision are historical; use only staging-root Reviewed-T05-Client-Cause-Command.ps1.txt and this review.

Command-file SHA256: 08709F146A56F54F021AD6FA7F11C6660C8AA4D8C5D50845EFFD5FEFCC3918C2
Admission SHA256: 5B8F8B830B17A0F4E2037D3C0E9AEE903207D71C43DCECC51B82D81D2563D044
Input-manifest SHA256: F94FE06950460E6FA557C1419AE7922029777EE610ED2B82DE9D81C9D800CA2F (23 entries)

Exact future command:

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-t05-client-cause-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 '5B8F8B830B17A0F4E2037D3C0E9AEE903207D71C43DCECC51B82D81D2563D044'
```

Ten ordered controls, 38 reported predicates: SUBJECT-PINS(1), RUNTIME-PROVENANCE(7), DIFF-REDERIVATION(2), PRESERVED-OUTSIDE-CHANGE(1), CHAIN-HELPER(5), OBSERVE-WIRING(4), STOP-PRODUCER-AND-VALIDATOR(7), BATCH-CONFIG(3), PRIOR-FAKE-APPLICABILITY(2), ACTUAL-SOURCE-MUTANTS(6). Four mutants are behavioral, two structural. Source mutation anchors are unique in whole text; failure oracles are related exact prefixes. Same guard/client identity, None fallback, unexpected exception identity, secret exclusion, bounded chain/frame export and fallback are behavioral extracted-source controls. Caller retirement/capture wiring is structural, not execution of the native caller.

One PowerShell/Python outer-admission/launcher/checker chain, one check child, two capture readers. The checker creates a disposable local temporary directory, writes and hashes fake owned Python source and a manifest, then removes that owned temporary directory. Exception objects/modules and fixture transport/TLS/DB/process operations are fake. Standard-library http.client may import socket/ssl, but no sockets or TLS contexts are constructed. No application/vendor package imports, PKI generation, providers, database, Docker, installation/build or native execution.

Limits: 120s child collection plus one 5s owned-child kill/wait plus two 5s reader joins = 135s nominal, excluding construction/startup, outer waits, file/hash/fsync/receipt work and OS latency. No separate outer timeout. 64KiB per child stream, 256KiB result. Partial runtime provenance only. Retain result/disposition receipts and outer output; child streams hash/count-only. Bounded owned-check-child termination on timeout/error/overflow included. Temporary-directory removal is the check's named normal owned-file retirement, not authority for any additional cleanup.

Require exact ordered ten-control PASS and 38 predicates, six targeted mutants detected by related oracles, zero child output and clean joined readers. Negative controls catch/assert their expected fake exceptions, including cleanup UNKNOWN within the diagnostic chain; they do not authorize a framework/retirement UNKNOWN. Stop on failure, mismatch, timeout, unexpected output or framework/retirement UNKNOWN. No retries, repairs, rerun, fallback or extra cleanup.

A PASS proves finite diagnostic fixture/source properties only. It cannot establish the failed native client class, TLS/EOF behavior, peer timing, or full T05. Existing producer follows explicit cause else context, including suppressed contexts; at most three exceptions, eight owned frames, 128 traversed frames and 4096 bytes, with truncation/original-kind fallback. Unowned native-library frames or deeper causes may remain unretained. No disclosure widening or classifier/stimulus change is approved.

Endpoint unbound. All execution remains held until Trish authorizes this exact one-shot card. Original packets and failure evidence preserved.
