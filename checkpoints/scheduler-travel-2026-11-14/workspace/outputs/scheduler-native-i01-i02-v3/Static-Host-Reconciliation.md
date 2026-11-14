# Native I01/I02 v3 — static host reconciliation

Dex, 2026-11-10 Pacific. Read-only source/JSON review and SHA256 only. No Python imports, compilation, checks, Docker commands, PKI generation or native launch.

All 268 payload manifest entries match. Manifest SHA256 312D6D5697402009E1EDB4C5B6CE20AA2A1BF439E37A6E429E6B43532ECF4858; launch-config SHA256 F0F5E88B75E9F28AB5DB61B9E9556A25C25860604BBD042C8532609D03830E18. Direct comparison with scheduler-c06-fake-v3/packet/payload found 267 identical files and only launch-config.json plus SHA256SUMS.txt changed. This preserves the exact C06 fixture bytes covered by the 39-control fake PASS; it does not convert that PASS into native evidence.

The host and runner configuration contain the same ordered 22 case IDs and the same expected UNKNOWN inventory: N06, N07, I01-C06. C06-MAP remains outside that inventory. Host invoke constructs Plan from the configuration and refuses launch_ready=false before creating an evidence directory. The future v3.evidence directory does not exist. No operator invocation has been prepared for this held draft.

Static host acceptance remains strict: full immutable container IDs; identity/state verification around starts and cleanup; runner exit zero; exact ordered case inventory, full passed count, zero skipped/failed/unexpected UNKNOWN, workers joined; post-run input hash check; report retained at suite_pass. Only that path removes runner and checks absence, SIGINTs DB, requires exit zero, removes DB and checks absence. Exception path records sanitized STOP/known IDs without cleanup or retry. The runner additionally requires a complete registry, matching case IDs/UNKNOWN semantics, joined per-case workers and no surviving threads. This is source review, not behavioral validation of those guards.

## Real C06 operations that must appear in the later launch disclosure

The unchanged prepared recipe runs as UID 65534 through absolute /bin/sh and /usr/bin/openssl. It creates a disposable 3072-bit RSA CA and server leaf, SHA256 signatures, two-day validity and native-fixture.invalid SAN, within an exclusive mode-700 /tmp/c06-gate-tls directory. Private keys remain there, mode 600; no database private key is transferred. Client gate trust uses the new runner CA, while backend database trust uses /public-ca/ca.crt. This temporary fixture identity does not bind the product endpoint.

The Python fixture owns one new process session/group and two capture readers. Declared generation/admission budget is 30 seconds, group retirement 5 seconds, and each of two reader joins 5 seconds: 45 seconds nominal total, subject to process/OS latency and the outer runner watchdog. Capture is capped at 64 KiB per pipe; fixture artifact ceiling is 1 MiB. Group probing and TERM/KILL target only the owned disposable child group. Reader outcomes/EOF, group retirement and pipe retirement must be known before success. Container cleanup is a separate success-only exact-ID operation. These real child operations have not been executed by this preparation.

Existing declarations remain 900-second suite, 600-second runner, 240-second fault gates, 64 Docker command cap, 1 MiB command/report capture, one CPU and 1 GiB memory+swap per container. No limit increase is authorized here.

## Remaining preparation and proof

Jim's T02 v1 source scope/hashes reconcile, but its fake verification authoring was returned for correction (T02-Preparation-v1-Independent-Review.md in scheduler-native-i01-i02-v1). Keep this native draft immutable and held. After the corrected T02 packet is independently reviewed and its separately authorized fake verification is proven, recommend carrying those four approved prospective files into a fresh combined native packet. Do not silently change this held draft or reuse a consumed launch approval. Re-audit the exact combined source lineage, registry, retained per-case evidence, complete manifest and final invocation before presenting the native launch card.

Post-run acceptance must inspect actual I01 ingress/dispatch/connector/native assessment fields, real C06 lost-ack gate receipts, ASGI disconnect receipts and I02 database-observed lock/PID/revision/generation coherence. Full per-case evidence, successful exact-ID cleanup and T01–T08 synthetic transport contracts remain required. Neither static host review nor the C06 fake PASS closes those obligations. Endpoint unbound; execution and all other holds remain.
