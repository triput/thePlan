# Exact-ID failure cleanup — native T05 diagnostic v2

Dex, 2026-11-13. One approved invocation stopped: runner125, outer1,12 Docker commands. Diagnostic captured SuiteStop at abrupt classification guard chained from BrokenPipeError at production JoinedTLS.receive sock.recv, source line112. Truncated class/location-only report; errno/message and deeper cause unretained. No native T05 PASS established. All307 input pins unchanged. Two read-only exact-ID inspect snapshots retained; frozen images,users,entrypoints/argv,isolation,tmpfs,network namespace and read-only mounts reconciled. No cleanup has run.

Use only same pinned Python5F7B89A6, Docker8985CD8A, immutable docker_transport.py7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53 and separately admitted docker-ops-config48653FB3D61EEB64886F9D60CE0FCCC943E6839221F1EE17B37E1614C8F41162 from scheduler-native-provider-t05-client-cause-launch-dex-v2. No launch command rerun.

Nine exact helper operations under300s shared admission,30s each:
1. check_identity runner fffb78a93543fa10464cb4b1f2dab95f643fd1380b0224e7c6bd86fed3279dc9; require exact frozen identity/config and exited125.
2. remove_exact runner, no force; require exact ID.
3. verify_absent runner; require true.
4. check_identity database5faa2b010d4f4cf222c52a9742549dfb8f5513ebf6f1645a94fe2eee1b02a2e1; require running and frozen config.
5. sigint_exact database; require exact ID.
6. wait_exact database; require exit0.
7. check_identity database; require same identity and exited0.
8. remove_exact database, no force; require exact ID.
9. verify_absent database; require true.

Initialize helper ownership with the two exact frozen IDs. Record every command/output hash and cleanup decision in a new exclusive receipt. Existing32-command helper cap and1MiB combined capture per command remain. Startup/file/hash/fsync/receipt work and OS latency excluded. Existing owned-CLI kill does not wait or establish daemon cancellation. Stop on any failure,mismatch,timeout or UNKNOWN; no force,retries,repairs,restart,rerun,fallback or extra cleanup. Preserve all failed evidence/public CAs/frozen inputs. Recheck307 inputs afterward.

This approval changes resource state. Original success-only cleanup authority did not cover this failed attempt. Endpoint unbound and all other holds stay. Microsoft-refresh and all other runs remain separately held.

Signed: Dex