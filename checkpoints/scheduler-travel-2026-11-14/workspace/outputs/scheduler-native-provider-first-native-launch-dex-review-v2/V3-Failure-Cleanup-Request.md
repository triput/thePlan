# Native provider v3 — exact-ID failure cleanup request

Execution authority remains held for this cleanup. The one native launch is consumed. Read-only reconciliation passed for both exact containers, with no identity/isolation/mount mismatch and265 input hashes unchanged. Preserved receipt SHA256 FC3822C3A1CA0DBD7F6903BDACB0E6F32E2553381044841B1B72AB3B73F63D6D.

Docker executable: C:\Program Files\Docker\Docker\resources\bin\docker.exe, SHA256 8985CD8AC002C3240B5AA48FE401FCB55DCA5D849B537E3C835564E8E8C49A70.
CLI config directory: C:\Users\trish\Documents\Codex\2026-10-15\trish-wants-to-improve-dex-s\outputs\scheduler-native-provider-first-native-launch-candidate-dex-v3\payload\docker-config.
Explicit Docker endpoint: npipe:////./pipe/dockerDesktopLinuxEngine.

Use those exact global Docker arguments for each command below. Stop immediately on any failure, mismatch, timeout or UNKNOWN. No force, retries, start, repair or rerun. Retain output hashes/counts, exit status and absence receipts. No command authorizes another container or a name lookup.

1. container rm 375621bd59780e2aaf7f9b83ec131c3a36afb5c785c3abab97842958caf74f56 — require returned exact runner ID. Reconciled state exited125.
2. ps -a --no-trunc --filter id=375621bd59780e2aaf7f9b83ec131c3a36afb5c785c3abab97842958caf74f56 --format {{.ID}} — require empty output.
3. kill --signal=SIGINT b1d965b4a1cafb74d3ca1ee894227fed4ef5965651f143b8f45f71a5d7859af7 — require returned exact DB ID. Reconciled state running.
4. wait b1d965b4a1cafb74d3ca1ee894227fed4ef5965651f143b8f45f71a5d7859af7 — require exactly0.
5. container rm b1d965b4a1cafb74d3ca1ee894227fed4ef5965651f143b8f45f71a5d7859af7 — require returned exact DB ID.
6. ps -a --no-trunc --filter id=b1d965b4a1cafb74d3ca1ee894227fed4ef5965651f143b8f45f71a5d7859af7 --format {{.ID}} — require empty output.

If a state recheck is needed before mutation, only read-only inspection of these exact IDs is permitted; a mismatch stops cleanup. The immutable reviewed Docker helper can enforce30s per command within a300s cleanup deadline; its existing owned-CLI termination/readers behavior and inability to prove daemon cancellation remain disclosed. No new helper behavior is approved. Failure cleanup is a new state-changing gate because the original run authorized cleanup on success only.

Save receipts under the existing candidate-dex-v3.evidence directory. Endpoint remains unbound; offline investigation does not authorize repairs or execution.
