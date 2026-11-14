# Reconciled native-provider authoring scope for Trish

Dex, November 12, 2026. Proposal only until Trish explicitly approves. This document governs authoring scope; no execution is requested.

## Review and selected direction

Jim v2 TIP 1D88A97FCD60BF65B95414044CEA3D90FCD110848C05B67E54DAC0BDA8C575F4, proposal F89B990CA1EA4FB89DD58756136F8972EF9AFAE00AE6150C9FD54EF936C9784B and registry BBFEF33312A4E532BCC0FD49BACAA40641C26F955F5862FD3192641621F15F05 are independently read. Eight frozen artifact hashes match both workspace and drop; TIP preimage verified; all 76 exact planning IDs are present. Integrity-Reconciliation.json records the limited integrity claim. Presence is not closure.

Accept v2's direction for bounded implementation preparation with the qualifications below. No further documents-only revision is required before this authoring decision. Jim leads coding; Dex reviews/integrates. One active assignment.

Use the production JoinedTLS default, vendor URL/port and verify-full with numeric loopback dial; no injection seam. Initial nonroot :443 bind uses unchanged isolation; a later authorized launch stops if unsupported. No capability/sysctl/root/network fallback is approved. Docker ownership stays on the host. Preserve native TOKEN versus IMPORT terminals, real ASGI disconnect versus provider EOF, 210/240/30 request clocks and 600s per-attempt plan validity. No failed-attempt reseed/retry.

## Exact prospective mutable roles

Fresh workspace root: outputs/scheduler-native-provider-prep-v1/. Preserve predecessors. Author only these paths beneath that root:

1. Invoke-Native-Provider.ps1 — host operator admission scaffold.
2. payload/fixture/np_supervisor.py — host-side supervision only; never imported as in-runner Docker authority.
3. payload/fixture/np_integrated_runner.py — in-runner admission/registry guards.
4. payload/fixture/np_runner_entry.py — in-runner entry.
5. payload/fixture/np_suite.py — finite declared cases and immediate STOP oracles.
6. payload/fixture/np_receipts.py — bounded sanitized evidence.
7. payload/fixture/np_provider_peer.py — synthetic peer implementation.
8. payload/fixture/np_provider_transcript.py — finite exchange scripts.
9. payload/fixture/np_provider_routes.py — fixture routes/trust only.
10. payload/fixture/np_auth_seed.py — disposable tokens/settings and per-case planning.
11. payload/fixture/np_alias_seed.py — disposable canonicalization seed.
12. payload/fixture/prepare-np-provider-tls.sh — recipe source only, no generation.
13. verify/check_native_provider.py — fake-only structural/fault-control checker.
14. verify/launch_check.py — bounded local check launcher.
15. verify/verify_admission.py — outer hash admission.
16. Invoke-Fake.ps1 — operator wrapper for a separately held verification.

Allow finite case/oracle/config/manifest/diff/review data and documentation, including launch-config.json and runner-config.json scaffolds. No extra executable preparation helper, optional DB wrapper, or unnamed mutable role. Reuse existing DB/bootstrap/Docker transport/runtime helper files as immutable copies with full raw hashes and paths in the handback. A required behavioral change outside these roles returns to Trish.

Approval would include routine same-contract corrections in fresh successor copies of these named roles, including after offline diagnosis of a failed run. Preserve every failed/frozen packet; no repair of the failed copy, automatic retry or rerun. This prevents routine preparation cards while retaining every execution gate.

## Exact source assembly proposed in the same authoring decision

Permit a workspace-only application copy at payload/api/ using the 234 source-file selection recorded in outputs/scheduler-investigation/Final-Assembly-Proposed-Source-Selection.json, SHA256 857141512AADF6F90F1CA8F92547A777E3D5FE943671495512FA18CEA7CBA296. Reverify every selected source before copying; stop on mismatch. This is assembly of selected bytes, not new application editing.

Base: scheduler-framing-ack-fake-v4/packet/candidate; sole override: scheduler-port-zero-fake-v1/packet/candidate/app/services/covering_transport_policy.py (5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88). Retain all other 233 base source files unchanged. Relative to passed I01/I02 v4, selection records 229 unchanged files and five deltas: covering_http_transport.py, covering_joined_https.py, covering_provider_context.py, covering_refresh_import.py and covering_transport_policy.py. Preserve the 13 critical unchanged entry contracts. Return the exact full-tree manifest and diff.

The port candidate remains unverified. Copying it for preparation does not authorize its run, claim it passed, or make the native packet launch-ready. No native launch review until applicable port result, assembled source lineage and all runtime/configuration pins reconcile. No repository integration, Git mutation, deployment or product endpoint binding.

## Required implementation qualifications

- Use the registry's 27 native STOP units and four pure-control witnesses as the initial inventory. Share setup/multiple immediate oracles where sufficient. If implementation requires different case grouping, explain it in the handback; no silent omission of any of the 76 requirements.
- NP-T05-ORDERLY-CLOSE must expose separate named observations for a complete close-delimited response accepted after orderly close_notify and for a valid-JSON prefix shorter than its declared Content-Length refused after orderly close_notify. A truncated length response alone cannot prove positive close-delimited support. Keep abrupt TLS truncation distinct. Do not repeat all 57 historical characterization cases natively.
- Retain T02 item/byte direct-overrun and T08 nested/reset gaps explicitly. Assign exact executed controls/source lineage where available, otherwise author focused fake witnesses in the named checker. Host-fake EXCESS-ITEM-BYTE and PRIMARY-BOTH-CLOSES are actual finite logical evidence; real socket/thread/deadline claims need their actual layers. No family-label reuse or implied waiver.
- T07 real-resource observations must be named individually; one grouped case label does not prove all cleanup variants. No artificial weakening of production guards to force close failures.
- Fresh planning for each distinct predeclared attempt; explicitly record capture/check clocks. Compute runner/suite/command/PKI/output/retirement bounds from actual operations before any launch card. Prefer incremental serial batch launches rather than one mega-suite. A runtime receipt is not supplied by this authoring approval.
- Source may implement bounded owned peer/PKI child/reader retirement, but any invocation and fault-retirement authority must be explicit in the later launch card. Failed-container shutdown/removal remains separately gated. Unjoined/unconfirmed retirement stops UNKNOWN.
- Correct the v2 documents' escaped control characters and malformed path spellings in fresh documentation. Use the exact path list above. Do not mutate the frozen v2 handback.

## Return and retained gates

Return exact source/assembly diffs, full hashes, immutable helper lineage, finite cases/expected outcomes, fake-only verification commands and limits, and disclosed remaining gaps. Dex independently reviews before presenting any launch.

No imports, compilation, tests, verification, helper invocation, Docker, sockets, certificate/key generation, installation, build, provider access, real credentials or execution under this preparation approval. No application edits beyond the exact selected-byte assembly. Endpoint unbound. All other holds remain.