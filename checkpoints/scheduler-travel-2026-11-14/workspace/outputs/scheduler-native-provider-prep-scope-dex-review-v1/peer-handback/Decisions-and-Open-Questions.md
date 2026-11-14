# Decisions and open questions — native provider prep scope (Jim)

Documents only. No approval ask in this file; lists unresolved items for Dex/Trish review of the concrete proposal.

## Proposed decisions embodied in the proposal (Dex may retain/revise)

1. **No new production JoinedTLS injection seam** — leave `CoveringReleasePlan` default factory; do not wrap with `FixtureByteTransport` for real-TLS claims.
2. **Finite native inventory = 25 executable cases**, preserving all 76 planning IDs via property-matched REUSE/HOLD/GAP.
3. **Serial batches B1–B5**, preferably as five separately authorized one-shot launches.
4. **Topology candidate** — unchanged vendor URL origin/port + numeric `127.0.0.1:443` + verify-full; recommend Alternative A for nonroot :443; STOP on bind failure; no URL rewrite/root/sysctl/port-translation fallback.
5. **Production clocks** 210s work / 240s request / 30s shared cleanup wherever those claims are made; supervisor timeout distinct.
6. **STOP** on failure/mismatch/timeout/unexpected UNKNOWN; no retry/repair/automatic failure cleanup.
7. **Token COMMIT survives later import rollback** — assert separately (existing source behavior).

## Open questions / dependencies (unresolved)

| ID | Item | Blocking? |
| --- | --- | --- |
| D1 | Framing-fake-v4 still with Trish — unexecuted | Final framing source + T05 byte-fake REUSE |
| D2 | Port-zero still with Trish — unexecuted | Port origin ID + policy lineage |
| D3 | Final assembled application hash set | Native workspace pins |
| D4 | Nonroot :443 alternative A/B/C/D | Vendor-origin composition claim |
| D5 | Trish fixture preparation card (wording drafted; not requested yet) | Any np_* authoring |
| D6 | T08 as one multi-oracle case vs three STOP units | Inventory freeze |
| D7 | Five launch cards vs one mega-suite | Budget / STOP isolation |
| D8 | Later launch command/hash/bounds freeze | Execution |
| D9 | T02 items/bytes overrun focused witness timing | Full T02 closure (disclosable post-beta per finish-line) |
| D10 | Peer mechanism (MemoryBIO/SSLObject vs OS socket) per case family | Peer design detail |

## Explicit non-decisions (not silently changed)

- Vendor URL builders unchanged.
- D2 path policy, Microsoft routing policy, header compatibility policy (`AEAE5343…` / `1C932F1A…`) unchanged by this proposal.
- Endpoint remains unbound.
- Fake packets are not PASS before authorized reconcile.
