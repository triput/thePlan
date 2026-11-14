# Draft — Trish source-preparation card wording (proposal text only)

This is **draft card text** for a later Trish decision. It is **not** an approval request in this handback. Do not treat this file as authorization.

---

**Card title:** Native synthetic-provider fixture preparation (authoring only)

**Question (when Trish is ready):** Approve Jim to author the native synthetic-provider fixture/packet files listed below in a fresh packet copy, under the bounds in Jim’s Implementation-Scope-Proposal?

**Authorize (if approved later):**
- Author only these prospective files under a new packet (name frozen at preparation), reusing I01/I02 v4 runner/DB patterns and pinned lineage:
  - `fixture/np_supervisor.py`
  - `fixture/np_integrated_runner.py`
  - `fixture/np_runner_entry.py`
  - `fixture/np_suite.py`
  - `fixture/np_receipts.py`
  - `fixture/np_provider_peer.py`
  - `fixture/np_provider_transcript.py`
  - `fixture/np_provider_routes.py`
  - `fixture/np_auth_seed.py`
  - `fixture/np_alias_seed.py`
  - `fixture/prepare-np-provider-tls.sh`
  - `fixture/prepare-np-db-tls.sh`
  - packet `launch-config.json` / `runner-config.json` scaffolds (unlaunched)
- Finite inventory: 25 native cases; all 76 planning IDs retained via REUSE/HOLD/GAP mapping in the proposal.
- Observe real default JoinedTLS (no FixtureByteTransport wrap for JoinedTLS claims).
- Fixture-only trust/SAN recipe; private keys tmpfs-only in disposable design.
- Distinguish nonexpired vs Google/Microsoft owning refresh; alias canonicalization vs routes; TOKEN commit vs later import rollback.

**Do not authorize by this card:**
- Execution, Docker run, sockets live, PKI generation outside reviewed disposable recipe, real providers/credentials, installation/build, endpoint binding, port/framing merge, URL rewrite, root/capability/sysctl/port-translation fallbacks, ambient secrets, 76-run Cartesian expansion, PASS claims.
- Application source edits in the 3-file covering lane (consume final assembled tree only after that tree is separately authorized).

**Flags after a future approval of this card alone:**
- `implementation_authorized=true` for listed fixture/packet authoring only
- `launch_authorized=false`
- `executed=false`
- `prep_is_not_pass=true`
- endpoint unbound

**Still required before any launch:** reconciled framing-fake-v4 and port-zero results; final assembled application hashes; topology :443 decision recorded; separately frozen command/hash/bounds launch packet(s).

**Proposal pin:** `Implementation-Scope-Proposal.md` (hash on ARTIFACT-HASHES / TIP-FREEZE when frozen).
