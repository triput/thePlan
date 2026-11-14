# Remaining gaps — native-provider prep-v2

Flags: `executed=false`; `launch_authorized=false`; `prep_is_not_pass=true`; endpoint unbound.

Frozen tipped prep-v1 TIP on-disk `0AA4C08197E897F8A91A23945D882854FED44528E476AF04506D245B2EDB211D` / tip_sha256 `31FC0AD8…` preserved as interim scaffolding (immutable).

## Port dependency (updated)

| Field | Value |
| --- | --- |
| Status | **VERIFIED finite host PASS 9/9** (extracted-class) |
| RESULT | `B8C6353A712382E16B601036034B32293EDEDF345388990D489B0E9AB9A12548` |
| Receipt | `61F266A34BF7E4BD8BD5193D3DB6A315F02C9C9AC13D4AC51F80C73C62720961` |
| Reconciliation | `E922DA6183B70D5DA9B1CBE19768F95E6B31578DA6B5594C2BD0CB5129861D7D` |
| Policy in assembly | `5F48FD7ED50C57A6A47ADA20138678BB3C112A2A69D1C234A47580E6CD068B88` |

Consumed verified PASS status for assembly. **Still not** native dial/TLS or full T01 closure.

## Explicit retained gaps

| ID | Disposition | Note |
| --- | --- | --- |
| T02-ITEMS-OVERFLOW | GAP | Host-fake EXCESS-ITEM-BYTE (RESULT 3905A070…; probes 8 bytes / 3 items vs 5) = reduced-limit logical evidence — not native 10k/16MiB overrun. Cite `T02-T08-Witness-Matching-20261112.md`. |
| T02-BYTES-OVERFLOW | GAP | Same reduced-limit host-fake scope; retained. |
| T08-NESTED | GAP_OR_FOCUSED_FAKE | ContextVar nesting; focused behavioral control in `verify/check_native_provider.py` (extracted selected defs). Not native foreign-thread proof. |
| T08-RESET | GAP_OR_FOCUSED_FAKE | ContextVar reset normal/exceptional; same checker. |
| T01-ORIGIN-FOREIGN-PORT | PORT_HOST_FAKE_PASS_NOT_NATIVE | Port PASS reconciled above; not native dial/TLS / full T01. |
| T07-BOTH-CLOSE-AFTER-PRIMARY-FAILURE | NATIVE case authored / body HOLD | `NP-T07-BOTH-AFTER-FAILURE` — host-fake PRIMARY-BOTH-CLOSES does not close. |

## Implementation HOLDs (prep-v2 increment)

First reviewable increment implements source for **NP-V-MS-NONEXPIRED** only (`np_runner_entry.IMPLEMENTED_CASE_IDS`). All other registry cases remain **explicit HOLD** (never fabricated PASS). Full 27+4 inventory + 76 planning IDs retained.

## Observation aids carried

- `Native-Deadline-TLS-Observation-Review.md` SHA256 `1A485EB29FD095933F0BA45A13B288A149E44FBFCEAFB26029C59C5D5F761069` + Source-Pins alongside
- `T02-T08-Witness-Matching-20261112.md`

Traps retained in suite/oracles/docs: ASGI budget admission clock; supervisor kill ≠ app deadline; `sent=True` uncertainty latch; peer prefix ≠ sender partial proof; ReleasePlan→Counter→CoveringHTTP→JoinedTLS; ASGI disconnect ≠ provider EOF ≠ task cancellation; dual T05 orderly observations; expected UNKNOWN never absorbs fixture STOP.

## Assembly / launch holds

- 234-file assembly re-verified; sole override policy pin unchanged.
- Runner/suite/command/PKI/output/retirement bounds not frozen — compute from actual ops before launch card.
- Invocation and fault-retirement authority = later launch card only (`launch_ready=false`).
- Failed-container shutdown/removal separately gated.
- Unjoined/unconfirmed retirement → UNKNOWN.
- No failed-attempt reseed/retry.
- Endpoint unbound; no product binding.
- Fake Commands-Held not invoked.

## Framing host-fake (not native proof)

- RESULT `3905A070AE06EF2EA6B31C8A8D1407A6F58E46B549E1118FF3928C00866ECBA3`
- Receipt `166BB080CCCD19B80F88703BA3CC16B46142DAEF3904BDAF5D7AA9CF3254E6E6`
- Do not promote to native TLS / owning-call proof.

## Open decisions (from jim-v2 TIP)

Unresolved decision IDs retained: D1, D2, D3, D4, D5, D7, D8, D9, D10, D11, D12. Resolved: D6.
