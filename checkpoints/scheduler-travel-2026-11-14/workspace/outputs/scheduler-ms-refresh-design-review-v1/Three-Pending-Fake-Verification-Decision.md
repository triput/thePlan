# Consolidated decision: three existing held fake-only verifications

This consolidates the three unanswered decisions; it adds no runs or source changes. Any approval permits at most one invocation of each exact packet, including replies to older cards. Duplicate replies never replenish one-shot authority. No execution has occurred.

Proposed sequence:peer-close,then T05 combined witness,then MS refresh merge. After each invocation independently reconcile its exact control/predicate inventory,exit/output/reader retirement and unchanged input pins before proceeding. Any failure,mismatch,timeout,unexpected output or UNKNOWN stops the sequence before the next run. Do not retry,repair,rerun,fall back or perform extra cleanup. Remaining invocations stay held after a STOP.

## peer-close

Command SHA256: 8B44B8BC0277A70A2E9B739C0DBE0BC840B7F63DB62E89B5DAB8D7C0DDD008C6
Input-manifest SHA256: 4D03B98A82592DA8A5E4B822985895A112CC0222245387AA4C5F4BDC7E92B1E8
Admission SHA256: 4104D6EBCEB4BB3DC4CFDC17C2905E2BDB4FA56A0B9E30619317DC6462589B9B
Verified inputs: 16; contained packet pins: 9; partial runtime pins: 1. Expected: 11 ordered controls / 35 reported predicates.

    & 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-peer-close-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 '4104D6EBCEB4BB3DC4CFDC17C2905E2BDB4FA56A0B9E30619317DC6462589B9B'

Independent review and detailed limits: C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-peer-close-fake-dex-v1\Review-and-Commands.md

## T05-combined-witness

Command SHA256: F03685858A7F098405E4A1726B52A9A20CE4B47F7DCF5211ECDF6D6B2EFEDB3E
Input-manifest SHA256: 299A509F255FDB492B9E8C9B50A1F84E2220951C25FDC42AB049C1D7254C0776
Admission SHA256: D07EE140C235B0E0024ECDFD0434C7E33BB174F6A41200D4C3F813B5A7FD632A
Verified inputs: 17; contained packet pins: 10; partial runtime pins: 10. Expected: 11 ordered controls / 40 reported predicates.

    & 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-t05-combined-witness-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 'D07EE140C235B0E0024ECDFD0434C7E33BB174F6A41200D4C3F813B5A7FD632A'

Independent review and detailed limits: C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-t05-combined-witness-fake-dex-v1\Review-and-Commands.md

## MS-refresh-merge

Command SHA256: 6BA1FE71F745CC503C05EE80C01FA65E684D5573A2A116D9D46E9A7FECF5CE11
Input-manifest SHA256: D18DF620242F99E4E1E87354EDDBA30CBD56671FFA6BD2BF4B919B048F0DAD8C
Admission SHA256: 095A2084B5709B6FADAE08F7CB250E4E27A1C6CFF37C705D3C237D74C92E3A22
Verified inputs: 28; contained packet pins: 21; partial runtime pins: 1. Expected: 9 ordered controls / 33 reported predicates.

    & 'C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-ms-merge-fake-dex-v1\packet\Invoke-Fake.ps1' -AdmissionSHA256 '095A2084B5709B6FADAE08F7CB250E4E27A1C6CFF37C705D3C237D74C92E3A22'

Independent review and detailed limits: C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-ms-merge-fake-dex-v1\Review-and-Commands.md

## Scope and limits for the combined decision

Peer-close uses extracted peer methods with byte-fake listener/client/TLS objects;no real socket. T05 combined witness executes unchanged transport/policy source with fake dependencies and the actual pinned host Python3.11 parser;its real standard-library socket/ssl modules may be imported transitively,without constructing sockets,SSL contexts or TLS connections. The merge checker parses subject source for structural/text identity and does not execute it. These finite checks do not establish native behavior. The native T05 revision remains separate.

Each invocation uses the reviewed local PowerShell/Python outer/launcher/checker chain,one owned checker child and two capture-reader threads. Per invocation:120s collection +at most one5s owned-child kill/wait +two5s reader joins=135s nominal. Three invocations total405s nominal collection/retirement if all proceed;startup/construction,outer waits,hash/file/fsync/receipt work and OS latency excluded. No separate outer or overall sequence timeout is claimed. Caps64KiB each child stream and256KiB result per invocation. Retain separate result/disposition receipts and outer hashes/counts;child streams hash/count only. Bounded owned-check-child termination on error/timeout/overflow is included in the proposed authority.

Runtime provenance:interpreter-only for peer-close and merge;ten partial runtime pins for T05,including its host parser sources. None is a complete DLL/standard-library/environment lock. Require exact ordered controls/predicates and precise negative/mutant oracles,exit0,zero child output,clean EOF/joined readers and known retirement.

No real application/vendor package imports,real sockets,TLS/PKI,provider/database/Docker access,installation/build,native launch,endpoint binding or activation. Actual selected source definitions execute only within the disclosed fake dependency environment. Preserve original/frozen/failed evidence. Existing execution hold requires explicit approval;preparation and review are not authority. Native and state-changing cleanup gates stay separate. Endpoint unbound;all other holds stay.

Signed: Dex
