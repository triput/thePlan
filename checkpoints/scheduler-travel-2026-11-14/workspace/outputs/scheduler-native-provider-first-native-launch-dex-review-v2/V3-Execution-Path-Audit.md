# Native v3 execution-path audit

Dex static source review, November 12. No target imports, helper invocation, Docker calls or native execution. Peer review and Trish launch approval remain held. This audit supplements V3-Static-Reconciliation.json; it does not alter the frozen packet.

Reviewed packet: scheduler-native-provider-first-native-launch-candidate-dex-v3. Input-manifest SHA256 26560DF4DF4C33E3FCB1B9A983F30BF8F1569AB0BC5C9D23EC7F892C17B31EAF.

## Configuration and admission

Reviewed-Command.ps1.txt supplies the absolute operator path and independent raw host-config and DockerOps-config hashes. The operator checks host interpreter/Docker executable hashes, manifest hash, each declared payload hash, staged readiness, external config placement and absence of prior evidence. The supervisor independently admits its manifest-pinned immutable helper before importing it; DockerOps verifies the exact payload set before a Docker call. The added empty Docker CLI configuration is included in that exact payload set and its directory is now explicitly supplied to DockerOps._cmd. No credentials or daemon settings are introduced.

The provider wrapper uses reuse_legacy_gate_protocol=False. It overrides attach and therefore does not read the inherited gate_seconds key or start gate_pair. The first batch has exactly NP-V-MS-NONEXPIRED and no expected UNKNOWN. Native T05 is not included. Runtime/image presence and nonroot port443 remain unproved until a separately authorized run.

## Static success-path command recount: 22

| Stage | Docker commands |
| --- | ---: |
| Inspect two exact images | 2 |
| Create DB; inspect created; start; inspect running | 4 |
| Readiness exec; transfer DB public CA; transfer negative-control public CA | 3 |
| Create runner; inspect created | 2 |
| Start/attach runner; inspect exited0 | 2 |
| Reinspect runner; remove; verify absence | 3 |
| Reinspect running DB; SIGINT; wait; inspect exited0; remove; verify absence | 6 |
| Total | 22 |

Pre/post verify_inputs are local hash work and add no Docker commands. The hard admission cap remains32; no additional probe or retry is implied. Each Docker command is recorded before spawning and checks the Docker executable again. Generic commands have30s caps; the provider attach uses runner_seconds600, all within the suite900s deadline. There is no separate outer timeout. File/hash/fsync work and OS latency remain outside nominal command supervision.

## Cleanup and stop behavior

The supervisor validates the exact case list, pass/skip/fail counts, joined_workers, unexpected_unknown and expected_unknown inventory, then verifies inputs again before recording suite_pass. Only that success path reaches removal. Cleanup uses retained full IDs, repeats exact identity/isolation checks, removes the exited0 runner without force and verifies absence, then SIGINTs the running DB, requires wait exit0, reinspects exited0, removes without force and verifies absence. Completion is recorded only afterward.

Any exception records stopped with known IDs and automatic_cleanup=false, then propagates. There is no failure-container cleanup in except/finally. The immutable command helper may kill its owned local CLI and briefly join its readers on command failure; it does not wait for the process after kill, so CLI retirement and daemon cancellation are not proven. The launch card must retain this qualification. No automatic repair, retry, alternative image, escalation of privileges or fallback is authorized.

## Postrun acceptance remains required

Independently inspect the actual receipt/report, not just process exit0: exact one-case inventory, real production ingress/dispatch/connector and native changed assessment evidence, exact synthetic exchanges and default JoinedTLS, runtime pins and public-CA equality, declared finite bounds, all owned worker/PKI dispositions, preserved inputs, both exact-ID absence checks and final complete receipt. A failure stops and permits read-only exact reconciliation; state-changing failure cleanup requires a separate card.

The prior16-control fake PASS supports its finite original preparation scope, not this later native entry or these runtime behaviors. T05 closure and the remaining transport cases remain open. No current Trish decision is requested before Jim's independent native-v3 review is reconciled.
