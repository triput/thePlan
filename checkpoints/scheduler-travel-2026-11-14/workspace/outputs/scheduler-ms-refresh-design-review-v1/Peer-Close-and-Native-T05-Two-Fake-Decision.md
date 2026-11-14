# Two next fake verifications — execution decision

Recommendation: authorize at most one corrected peer-close v2 invocation, reconcile it, then at most one native-T05 fixture fake v2 invocation. Stop the sequence before the second invocation on any failure, mismatch, timeout, unexpected output or UNKNOWN. This is new authority for two unexecuted packets; earlier one-shot grants are consumed.

| Packet | Command SHA256 | Input-manifest SHA256 | Admission SHA256 |
|---|---|---|---|
| Peer-close fake v2: 11 controls, 35 predicates, 4 mutants | A39C65DE2F44328545FF646B3F623CF4F26F8783E3C228B490A7EBD615F3EFD0 | C90EF9D0F0238220BECEE01113065E033537B4934037994105EDAF3506033C32 | 95B8BF6A3D61C4F7D2F7FD490B7B0A71232941D6FBBA7162B19326F3DDBA246C |
| Native-T05 fixture fake v2: 14 controls, 74 predicates, 10 targeted mutants | 0FBE49FCA90945B4D2565C6BC3767E51A5CFAE5F262F2FA183F70A5A59691B7A | EB3D256C12D245B1EB931BC80FBF632C342DF249FFE816B86F4272C42655D04E | 97DC6603A7749889CE0723AB41CCDF2AE0CF268C1D7C65F1759CFC22B7BF49C0 |

Exact commands are these two files, in order:

1. C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-peer-close-fake-dex-v2\Reviewed-Peer-Close-Command.ps1.txt
2. C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-t05-fake-dex-v2\Reviewed-Native-T05-Fake-Command.ps1.txt

Their adjacent Review-and-Commands.md documents describe scope and limits. Only those Reviewed commands are current. Copied earlier commands, Launch-Decision documents and preparation freezes are historical. In particular the peer-close v2 review's statement that the two earlier fake checks were unrun is an earlier snapshot; those now have independently corroborated PASS 11/40 and PASS 9/33 results. They are not repeated by this decision.

Matt's peer-close review 831FED1E59D25C89600D443F30263D5A35B6E4ABAC0F81D344A9A9872FB90C1C has no static blockers; all 17 review pins match. The peer checker differs only by its approved-lane marker-indent correction. Stopped v1 and all failed evidence are preserved. This v2 has never run.

Dex independently reviewed Matt's native T05 v3 code/checker. The final JSON admission check caught two unescaped Windows paths. The original 33-input source and incomplete first staging are preserved. Fresh T05 fake v2 corrects only those data spellings, machine staging booleans and the dependent outer pin. All executable/subject/EXPECTED bytes stay unchanged. All 37 staged inputs, 28 packet pins and ten partial runtime pins match. No checker has run. Review reconciliation: Native-T05-V3-and-Peer-Review-Reconciliation.json, SHA256 3D1FD47052820500AA2915D75A1B697787DC7D6590BA8EF7897DDF67241859B0.

Each invocation uses the reviewed local PowerShell/Python admission-launcher-checker chain, one checker child and two capture readers. Each permits 120 seconds collection plus at most one five-second owned-child kill/wait and two five-second reader joins: 135 seconds nominal each, 270 for both. Construction/startup, outer waits, file/hash/fsync/receipt work and OS latency are excluded; no separate outer or sequence timeout. Per invocation: 64 KiB per child stream, 256 KiB result. Bounded owned-check-child termination on error/timeout/overflow is included in the requested authority. Retain result/disposition receipt and outer hashes/counts; child streams hash/count only.

Peer-close has interpreter-only runtime provenance. T05 pins ten runtime files, a partial environment lock, and uses the actual host HTTP parser/JSON with fake transports. It may import stdlib socket/ssl without constructing sockets or TLS contexts. No real application/vendor package imports, real sockets, PKI, providers, database, Docker, installation/build or native execution.

Require exact control/predicate inventories, precise negative/mutant oracles, zero child/outer output, exit zero, known retirement, two clean EOF/joined readers and unchanged input pins. Reconcile the first result, retirement, authority and post-run pins before admitting the second. No retries, repairs, rerun, fallback or extra cleanup.

These finite fake results will not prove native TLS, real peer retirement, full T05 or full T01–T08. The fixed-length positive proves completeness, not client-observed close_notify; structural mutant checks are distinguished from behavioral ones. Native launches remain separately held. Endpoint unbound; all other holds stay.

Signed: Dex