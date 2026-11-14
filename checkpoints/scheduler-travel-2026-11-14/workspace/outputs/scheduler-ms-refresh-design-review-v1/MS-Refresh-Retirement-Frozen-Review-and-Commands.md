# MS-REFRESH retirement correction — finite fake verification review

Dex,2026-11-13. Qualified static acceptance; no remaining static blocker found for this scope. Matt handback13A388F0 and diff55C33990 match their two exact one-entry SHA sidecars. All301 native-preparation inputs,24 fake-preparation inputs,21 packet pins and10 partial runtime pins match. Independent source review confirms234 application files and250 other executable files unchanged; runner text outside _run_np_v_ms_refresh is byte-identical.

The two-hunk selected-body correction replaces the pre-join snapshot in place with attempt latch -> existing helper -> done flag, and removes the duplicate late retirement block. The old joined-only guard is replaced by the unchanged helper's stronger joined=True AND worker_error_kind=None predicate; its old error-message text is not claimed preserved. Other assertions, token rotation/persistence/expiry/native terminal/five-exchange/readiness predicates, setup, exception handlers and finally guard are unchanged. No T05 diagnostic or T03 merge.

Staging root: outputs/scheduler-native-ms-refresh-retire-fake-dex-v1. Twenty-two of24 source inputs are unchanged. Only outer/admission data change for future admission flags and the outer pin; all executable,subject and EXPECTED bytes unchanged. Current command is staging-root Reviewed-MS-Refresh-Retirement-Command.ps1.txt. Copied Future-Command-HELD.ps1.txt and Launch-Decision.md are preparation history; packet labels/inherited false-authority prose do not override the reviewed command/hash or human gate.

Command SHA256:7B617AC019D5AD2D5AD5BD02DDC3258073F8897B80EE1AC4AD45DEE128D7BAC2
Admission SHA256:DE4C94308F1E44FD72E56086F6F9EF4E93FF938B5AD59DA8739D411F635E5F1A
Input-manifest SHA256:157C6863BA157298E910439D9FF71B8E4F8124B665A7331AFF54918B13EF6CCF (27)

```powershell
& 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-ms-refresh-retire-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 'DE4C94308F1E44FD72E56086F6F9EF4E93FF938B5AD59DA8739D411F635E5F1A'
```

Ten ordered controls/41 reported predicates: SUBJECT1,RUNTIME7,DIFF2,PRESERVED2,HELPER7,BARRIER4,ASSERTIONS3,BATCH6,PRIOR2,MUTANTS7. Helper behavior uses actual extracted unchanged source and a named fake peer that publishes its final row during join. Caller wiring/assertion comparison is structural, not a run of the full refresh body. Seven actual-source mutants have unique whole-source anchors and precise related oracles: three behavioral,four structural. Prior selected-retirement13/85 helper properties map by exact source; its other caller-body claims do not transfer.

One local PowerShell/Python admission/launcher/checker chain,one check child,two capture readers. Actual host parser may import standard-library socket/ssl, but no sockets/TLS contexts are constructed. Fixture transports/processes/DB operations are fake; no app/vendor package imports,PKI,providers,database,Docker,installation/build or native run. Ordinary result/receipt file writes and hashing are included. No extra temporary fixture-directory lifecycle in this checker.

Limits120s child collection +one5s owned-child kill/wait +two5s reader joins=135s nominal,excluding construction/startup,outer waits,file/hash/fsync/receipt work and OS latency; no separate outer timeout.64KiB per child stream,256KiB result; partial runtime provenance only. Retain result/disposition receipts and outer output; child streams hash/count-only. Include bounded owned-child termination on timeout/error/overflow.

Require exact ordered10-control PASS/41 predicates,precise mutant/negative-control oracles,zero child output and clean joined readers. Named negative controls catch/assert fake retirement errors; any unexpected output,framework/retirement UNKNOWN,failure,mismatch or timeout stops. No retries,repairs,rerun,fallback or extra cleanup.

A PASS establishes finite helper/source properties only. Native refresh,T06 closure,peer timing and worker scheduling remain unproved. Syntax/behavior has not run. All predecessors and failure evidence preserved. This is a separate decision from the unchanged T05 diagnostic fake card and T03 D1 design card. No native authority is added. Endpoint unbound;all holds stay.
