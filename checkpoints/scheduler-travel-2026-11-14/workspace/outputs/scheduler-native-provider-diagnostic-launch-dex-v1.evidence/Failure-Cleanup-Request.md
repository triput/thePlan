# Native diagnostic attempt: exact-ID failure cleanup decision

The authorized one-shot native attempt is consumed. It stopped with runner CLI exit125 and validated location/class-only `SuiteStop` diagnostic at manifest-pinned fixture/np_runner_entry.py line971. That line refuses a covering-refresh HTTP status other than200. The actual status and response body were not retained; no cause or native PASS is established. No success cleanup ran.

Read-only reconciliation used the unchanged helper SHA256 7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53 and exactly two inspect calls. Both exact containers match their frozen identities, image, labels, entrypoint/argv, users, namespace, isolation, binds, mount projections and tmpfs settings. Database is running; runner exited125. Full inspections and reconciliation receipt are retained beside this request.

Proposed cleanup only, requiring Trish's separate state-change approval:

1. Recheck runner identity and exited125 state. Remove exact runner `945167db8cdeb3aa97ba4431b0aa527887d61d14c9c965fe05fd0db8963e258e`; require returned exact ID; verify absence.
2. Recheck DB identity and running state. SIGINT exact DB `a6f7c8ae571b843d4bc98d026670d30eb5204fd2e5e5657e2f9b52827cd58f55`; require returned exact ID; wait and require exit0.
3. Recheck DB identity and exited0 state. Remove that exact DB; require returned exact ID; verify absence. Retain the receipt.

Use only the same pinned Docker executable (8985CD8AC002C3240B5AA48FE401FCB55DCA5D849B537E3C835564E8E8C49A70), explicit endpoint npipe:////./pipe/dockerDesktopLinuxEngine, unchanged Docker helper and exact frozen host/docker-ops-config.json D89686D3754AB51632AB9C5F59B41270FCD1A85D0E92A82BF4F4044EBF593436 in outputs/scheduler-native-provider-diagnostic-launch-dex-v1/scheduler-native-provider-diagnostic-launch-v1. The helper supplies the admitted private Docker CLI config directory. Scope is nine Docker calls: three identity inspections plus six state/absence operations.

30s per command inside a300s cleanup deadline. Existing helper fault-termination/reader qualifications remain: an owned CLI kill does not wait or prove daemon cancellation. Stop on failure, mismatch, timeout or UNKNOWN. No force, retries, restart, repairs, rerun, fallback or additional cleanup. Product endpoint stays unbound; all other holds stay. This approval would cover container disposal only; offline trace remains separately within the standing read-only lane.
