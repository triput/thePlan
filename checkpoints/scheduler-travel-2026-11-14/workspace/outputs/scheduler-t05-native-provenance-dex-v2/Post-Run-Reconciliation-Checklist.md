# Native source collection post-run reconciliation

Prepared offline by Dex for the held native-dex-v2 packet. This document authorizes no invocation. Run only after independent review and Trish's separate exact-hash approval; preserve every output on any failure. No retries or source repair under the same launch approval.

## Admission and attempt

Verify the approved exact command hash and SHA256SUMS hash against the approval receipt. Confirm four packet rows,25 explicit runtime rows and the Docker executable pin before invocation, with a fresh evidence directory. Retain exact operator/tool output and whether the attempt was admitted, refused, started, failed, interrupted or completed. Do not report a pin refusal as a collected-source run. The unbudgeted file/hash admission and OS latency are distinct from the command supervision budget.

## Seven commands and owned identity

Read receipt.jsonl rather than inferring success from the host exit code. Require one attempt and exactly these seven admitted command/output pairs in order, with no extra command and no retries:

1. image inspect: exact c220110432cf4adbb4005518a02808b754e0efb050b5de202e71872fecdbd2ab, Linux, amd64, no declared volumes.
2. create: one complete64-hex ID. Preserve created event and compare the subsequent full identity; label native-dex-v2, user65534:65534, image, sh entrypoint and exact collector path. The label is not authority to remove any other ID.
3. inspect: created and not running/OOMKilled; exact network-none/read-only/nonprivileged resource/isolation/mount declarations. Verify host Binds and top-level read-only packet projection; no extra mounts/tmpfs/device/capability/port authority. Keep the actual inspection as evidence.
4. start --attach that exact ID once: exit0, complete bounded byte envelope, empty stderr, both capture readers at EOF and joined; no timeout, capture/interrupt/retirement error. Host CLI exit alone cannot prove this.
5. inspect the same ID/config again: exited0, not running/OOMKilled. No cleanup on any failure/mismatch/UNKNOWN.
6. rm that exact stopped ID only after complete envelope, saved-byte and post-collection pin verification: exact full-ID output, exit0, clean capture retirement. No force or wildcard cleanup.
7. exact full-ID absence filter: empty successful output, clean readers/exit0. A failed inspect or generic not-found diagnostic is not an accepted absence proof. Require the complete event after this step.

Every command output event must retain capture filenames/lengths/SHA256, complete true, CLI exit confirmed, readers_joined true, EOF tags[0,1], no reader errors, no primary fault or retirement_faults and exit0. Independently hash the raw .stdout.bin/.stderr.bin files and compare receipt sizes; check768KiB stdout/64KiB stderr limits. Partial captures on a stopped attempt are evidence of incomplete capture, never valid source provenance. Native command timing is30s each,60s attach,300s shared supervision/admission; one5s local CLI kill/wait and two5s reader joins are nominal fault retirement outside that budget. CLI termination does not prove daemon cancellation.

## Exact three-file bytes

Inspect command04.stdout.bin: exact kindT05-NATIVE-SOURCE-BYTES-V1; exactly three file rows in approved order, no extra path or duplicate:

- /usr/local/lib/python3.12/http/client.py -> http-client.py.source
- /usr/local/lib/python3.12/ssl.py -> ssl.py.source
- /usr/local/lib/python3.12/email/message.py -> email-message.py.source

Decode each retained base64 payload as data only when allowed as ordinary receipt reconciliation; never import/compile/execute a captured file. Independently compare decoded lengths/hashes with the envelope, source_saved events, actual retained raw .source files and RESULT.json rows. Require nonempty <=128KiB per file, <=384KiB raw aggregate; received envelope <=768KiB. Saved source sizes/hashes must equal the independently checked bytes; file existence alone is insufficient. Check no other source path was collected and all host source/reference files remain unchanged. Do not normalize source line endings or substitute upstream bytes.

The source_saved events precede removal, and any save/hash mismatch must have stopped before rm. Retain actual byte/hash provenance from the exact image even if it differs from host/upstream; a difference is evidence to interpret, not permission to repair or rerun.

## Durable result and retained inputs

Require RESULT.json statusPASS, kindT05-NATIVE-SOURCE-PROVENANCE, exact image/container ID, removed_and_absent true, commands7, behavior_proven false and exact source rows. Compare actual result length/hash to completion receipt. Independently rehash four packet files, runtime pins, manifest, operator commands and Docker executable; no drift. Peer-review and Trish approval hashes remain attached to this exact packet. Preserve raw command streams, inspections, three source files, result and receipt together.

If the attempt failed, only authorized read-only reconciliation may follow. A state-changing failure cleanup needs its exact reviewed approval; no retry/repair/fallback/additional container signal is implied. Report known IDs and partial resource/source/capture state honestly. Do not manufacture missing evidence with a second collection.

## Attribution and next safe work

A passing collection proves only the retained native source byte/provenance records and successful exact-ID resource cleanup. Host3.11 behavior, published3.12.16 reference and captured native bytes remain separate. It does not establish actual parser outcomes, TLS close_notify versus abrupt EOF, production OAuth rotation/native terminals, ownership/thread/request timing or full T01–T08 proof.

After independent reconciliation, source-only comparison of exact native parser/SSL/message implementations can refine the later synthetic fixtures. Any source correction or later invocation still follows its applicable gate. Endpoint stays unbound; all other holds remain.