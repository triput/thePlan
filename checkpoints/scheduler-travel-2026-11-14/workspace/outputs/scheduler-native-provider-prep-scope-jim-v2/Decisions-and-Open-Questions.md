# Decisions and open questions — native provider prep scope jim-v2

Documents only. No approval ask in this file.

Preserves immutable jim-v1 TIP 531BFBDE… / tip_sha256 2ED4F5DC… / Proposal 126AC17B….

## Proposed decisions embodied in v2 (Dex may retain/revise)

1. **No new production JoinedTLS injection seam** — leave CoveringReleasePlan default factory.
2. **Canonical native inventory = 27 STOP units** (+ 4 pure CF witnesses); all 76 planning IDs mapped in Case-Registry.md.
3. **T08** packaged as one multi-oracle case NP-T08-OWNERSHIP (Dex R2 accepted grouping).
4. **Topology default** — existing unchanged isolation as initial nonroot :443 attempt + bounded bind probe + STOP if unsupported; namespace/sysctl/cap are contingencies only.
5. **Production clocks** 210 work / 240 request / 30 shared cleanup; 600s plan validity with fresh planning per distinct predeclared case/attempt or split batches; never reseed/retry failed/expired attempt.
6. **Host Docker ownership** separate from in-runner 
p_integrated_runner (registry/guard only).
7. **Owned-resource retirement** distinct from container failure disposal; fault retirement only if later launch card explicitly requests one bounded attempt.
8. **STOP** on failure/mismatch/timeout/unexpected UNKNOWN; no retry/repair/automatic failure cleanup unless launch card says otherwise.
9. **Token COMMIT survives later import rollback** — assert separately.
10. **Framing-fake-v4** is PASS 73/73 at host-fake scope only — not native proof; does not authorize assembly/merge/launch.

## Open questions / dependencies (unresolved)

| ID | Item | Blocking? | v2 note |
| --- | --- | --- | --- |
| D1 | Framing reconcile into final assembled source (run already PASS) | Final framing bytes in assembled tree; T05 host-fake REUSE already citeable | **Updated:** executed PASS 3905A070… / 166BB080…; still not native; assembly not written |
| D2 | Port-zero one-shot authorize → run → reconcile | T01-ORIGIN-FOREIGN-PORT; policy lineage | Still unapproved/unexecuted |
| D3 | Final assembled application source set + hashes | Native workspace mount pins | Cite data-only selection 85714151… (229/5/13); no merge inferred |
| D4 | Whether contingency A/B is ever needed after unchanged-isolation bind attempt | Vendor-origin claim if initial bind fails | Default path no longer presupposes A |
| D5 | Trish fixture preparation card | Any np_* authoring | Wording revised for R5/R8 |
| D6 | ~~T08 packaging~~ | — | **Resolved by Dex R2:** one multi-oracle case OK |
| D7 | Separate launch cards vs mega-suite (incl. per-stall split for plan validity) | Budget / STOP isolation | Recommendation: separate one-shots |
| D8 | Native launch command/hash/bounds freeze | Execution | Later gated |
| D9 | T02 items/bytes direct overrun focused witness | Full T02 closure | **Not waived** by post-beta label |
| D10 | Peer mechanism (MemoryBIO/SSLObject vs OS socket) per case family | Peer design | Both must speak real TLS records to JoinedTLS for T03/T04/T05 L4 |
| D11 | Whether later launch explicitly includes one bounded owned peer/PKI-child/reader retirement on fault | Fault retirement envelope | Must not be quietly granted |
| D12 | Whether CF witnesses (USERINFO/FRAGMENT/CONTROL-CHAR/PURPOSE-WRONG) share a launch with native cases or run as B0 | Suite packaging | Registry includes them either way |

## Explicit non-decisions

- Vendor URL builders unchanged.
- D2 path policy, Microsoft routing policy, header compatibility policy unchanged by this proposal.
- Endpoint remains unbound.
- Host-fake PASS ≠ native PASS.
- No Slack tip from this seat.
