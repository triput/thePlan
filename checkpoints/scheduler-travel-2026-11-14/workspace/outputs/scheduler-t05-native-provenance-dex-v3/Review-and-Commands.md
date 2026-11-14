# T05 native source collection — held independent review

Dex, November 11, 2026. Fresh v3 preserves unexecuted v1/v2. V3 retains the admitted packet path/hash pairs and rechecks the approved manifest hash before cleanup; no freshly read inventory can replace the admitted comparison. It inherits v2 reader-join, saved-source and durable-result checks. Limits and collection scope are unchanged. Workspace-only authoring of the two native roles under approved scope20B9347FECC7597FC7DAA16AD92D8E3D45C1E4BC26B4DEFA929D1C58F3A42734. Jim retains the four framing roles and will independently review these native files. All Jim v1–v3 files and evidence are preserved. No Python/helper imports, compilation, tests, serialization probes, Docker or collection were performed in this preparation.

## Concrete behavior

collect-parser-sources.sh uses the retained runner's /usr/local/bin/python3 -I -S -B to read exactly the three approved sources. Standard-library base64/hashlib/json perform a bounded nonsecret byte envelope; no app/vendor imports, database/server/test/provider or network work. Source reads are limited to128KiB+1 each, aggregate384KiB. Each file must be nonempty and within128KiB. Output is capped768KiB and contains path/size/SHA256/base64. These chosen limits are refusal thresholds, not claims about unknown native sizes. No writes inside the read-only container, no writable bind, no tmpfs or PKI. Actual retained source bytes are written exclusively to the fresh host evidence directory after validation.

verify_native_provenance.py adapts the retained runner-only-v3 verified source-collection/process pattern. It validates inputs, host executable pins,25 explicit runtime pins and refused ambient Docker configuration; creates fresh evidence; then admits exactly seven Docker commands:

1. Inspect exact image ID and Linux/amd64/null-volume metadata.
2. Create one owned nonroot runner with exact image, labels, /bin/sh entrypoint and collector command; --pull=never, network none, read-only root, ro packet bind, cap-drop ALL/no-new-privileges, no restart/logging/healthcheck,256MiB memory+swap, one CPU,32PIDs. No image build/load/tag.
3. Inspect exact ID, image, user, label, entrypoint/cmd, state created, isolation and mounts before start.
4. Start/attach exact ID once; capture and validate complete three-file envelope. No retry.
5. Inspect exact ID/config again; require exited0 and not OOMKilled. Save raw validated files and hashes; recheck packet/runtime pins.
6. On success only, remove that exact stopped ID; require matching removal output.
7. Verify absence using exact full-ID ps filter, and save final receipt/result. No force or container cleanup on failure.

## Limits and custody

300-second command-admission/supervision deadline,30s per command except60s start/attach. A command fault admits at most one owned CLI kill/wait5s and two reader joins5s each:15s nominal retirement beyond the command budget. File/hash/fsync operations and process/OS latency are excluded; this is not a hard315-second wall-clock bound. Captures bounded during collection:768KiB stdout and64KiB stderr per command, queue32 chunks of4KiB,1MiB result limit. At seven commands, bounded retained command streams plus384KiB raw sources/result/receipt remain below an estimated8MiB; no hard filesystem quota is claimed. Any overflow retains partial capture marked incomplete and stops; no clipped capture is accepted as source evidence.

Each subprocess has fresh custody, two readers, EOF tags, joined/exit confirmation, capture hashes/sizes, primary fault and retirement errors. Local CLI termination does not establish immediate Docker daemon cancellation; on failure the known container ID remains for separately allowed read-only reconciliation and gated state-changing cleanup. No failure removal, restart, retry, repair or fallback is included. Fresh evidence root and exclusive files prevent replay; timeout/reader/capture mismatch never continues to cleanup.

Commands.ps1.txt contains the exact held operator sequence. It hashes the manifest/four packet inputs, explicit host runtime files and Docker executable before Python starts; refuses an existing evidence directory. It has NOT been invoked. Manifest pins the collector, supervisor, empty Docker config and runtime-pin data. Runtime provenance is explicitly partial; it is not a complete interpreter dependency closure or an immutable filesystem claim.

## Independent review required before a launch card

Read both new files and the full operator command. Trace every branch, its clock/capture/reader retirement, seven-command count, image/identity/mount/state requirements, complete-byte transfer, exact path inventory and source hash verification. Compare the adapted process pattern with the retained runner-only-v3 source; review late reader/close errors and failure-stop behavior. Check no required step is a descriptor/stub. Check commands use the exact new packet root. Reconcile image identity and Docker's retained projection conventions without broadening allowed differences. Rehash all packet/runtime/operator pins and fresh output absence. Confirm no execution by preparation.

A later one-shot launch needs Trish's separate approval of exact commands/hashes/limits, owned CLI timeout termination and success-only exact-ID removal/absence check. This packet establishes native source bytes/provenance only if it passes; no framing behavior, TLS EOF, request timing, provider retirement, native transaction or remaining T01–T08 family is closed. Endpoint unbound; all other holds stay.
V3 successor delta: only the packet label/root and the manifest-continuity guard change executable behavior. Collector and runtime data remain byte-identical. Jim's independent review is pending; this copy is not launch-ready. No packet invocation, import, compilation, test or Docker action was performed.
