# Selected Microsoft retirement correction: held fake verification

Only Reviewed-Command.ps1.txt in this staging root is current. Copied Launch-Decision.md, Future-Command-HELD.ps1.txt and source manifests describe preparation/history. Neither data admission flag authorizes a run.

Dex independently reviewed Matt's signed handback 4138F3AD and32 sidecar pins. The297 invalid,291 NONEXPIRED and45 fake source inputs match;41 packet and10 partial runtime pins match. Source changes are the selected fixture retirement barrier only;234 API files per native variant are unchanged. Static review BCDF0382 records scope and limitations.

This staging copy changes only OUTER and VERIFICATION launch_authorized booleans, plus the required OUTER pin. All checker, subjects, assertions, EXPECTED, wrapper, outer implementation and launcher bytes remain unchanged. Original packets and failed evidence are preserved.

## Exact invocation (HELD pending one explicit Trish approval)

    & 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-ms-selected-retirement-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 'CDC8F7721BF250BEF7D48481219295EBB76C70F978C7D1F80D5538DEFDEB753A'

Command-file SHA256: 913D9951C763DD8E81DEC696864BDD4EBC336CE8F1C46C292B21531A99CE4D23
Admission SHA256: CDC8F7721BF250BEF7D48481219295EBB76C70F978C7D1F80D5538DEFDEB753A

One local PowerShell/Python admission-launcher-check chain, one owned checker child and two capture readers.13 ordered controls/85 reported predicates, retaining all prior invalid-grant controls. Six new helper behavior cases use the exact extracted retirement helper with a fake peer; selected caller ordering is structural. Fourteen source mutants comprise seven behavioral and seven structural controls.

The actual host HTTP parser and extracted/isolated covering definitions run with fake dependencies. Standard-library socket/ssl imports may occur; no real sockets or SSL contexts are constructed. No application/vendor package imports, PKI, providers, database, Docker, installation, build or native run.

120s child collection +one5s owned-child kill/wait +two5s reader joins =135s nominal, excluding construction/startup, outer waits, file/hash/fsync/receipt work and OS latency. No separate outer timeout.64KiB per child stream,256KiB result. Partial runtime provenance only (10 pins). Retain result/disposition receipt and outer output; child streams hash/count-only. Bounded owned-check-child termination on error,timeout or overflow is included.

Require exact13-control PASS and85-predicate inventory, precise negative-control oracles, zero child output and clean joined readers. Expected fake application exceptions are caught and asserted; any unexpected output,failure,mismatch,timeout,framework or retirement UNKNOWN stops. At most one invocation. No retries,repairs,rerun,fallback or extra cleanup.

No native behavior is proved: TLS, peer timing, PostgreSQL terminal, persisted credentials and ASGI response remain held. MS-REFRESH's analogous retirement gap remains open. Old native card A50C04FB remains withheld; earlier approval transfers to no successor. Endpoint unbound; all other holds stay.
