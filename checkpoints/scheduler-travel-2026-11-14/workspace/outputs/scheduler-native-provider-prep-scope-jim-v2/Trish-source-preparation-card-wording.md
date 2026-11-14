# Draft — Trish source-preparation card wording (jim-v2 proposal text only)

This is **draft card text** for a later Trish decision. It is **not** an approval request in this handback. Do not treat this file as authorization.

Preserves immutable jim-v1. Addresses Dex R5/R8 authoring boundary.

---

**Card title:** Native synthetic-provider fixture preparation (authoring only)

**Question (when Trish is ready):** Approve Jim to author the named fresh-copy fixture/packet roles below in a fresh packet copy, under jim-v2 Implementation-Scope-Proposal + Case-Registry bounds, including only routine same-contract corrections needed to match those frozen roles?

**Authorize (if approved later):**
- Author only these prospective files under a new packet (name frozen at preparation), as **fresh copies** with lineage pins from I01/I02 v4 / seams docs:
  - Host operator entry scaffold Invoke-Native-Provider.ps1 (Docker/hash gates on **host only**)
  - ixture/np_supervisor.py — **host-side** container admission/cleanup authority pattern (not in-runner Docker)
  - ixture/np_integrated_runner.py — **in-runner suite registry/guard only** (loopback/nonroot/CA/inventory); does **not** own Docker; never mounts Docker socket
  - ixture/np_runner_entry.py
  - ixture/np_suite.py — exact inventory from Case-Registry (27 native + 4 CF witnesses)
  - ixture/np_receipts.py
  - ixture/np_provider_peer.py
  - ixture/np_provider_transcript.py
  - ixture/np_provider_routes.py
  - ixture/np_auth_seed.py — reuse I01 plan-clock pattern (capture_plan_instant / ssert_plan_still_valid / 600s validity); no reseed of failed/expired attempts
  - ixture/np_alias_seed.py
  - ixture/prepare-np-provider-tls.sh — fixture CA/SAN; tmpfs private keys
  - Reuse unchanged DB/bootstrap helpers (ootstrap-postgres-tls.sh / I01 postgres TLS pattern) rather than a parallel stack; only author a thin prepare-np-db-tls.sh wrapper if same-contract naming requires it
  - packet launch-config.json / 
unner-config.json **scaffolds only** (unlaunched; hashes not execution authority)
- Observe real default JoinedTLS (no FixtureByteTransport wrap for JoinedTLS claims).
- Distinguish nonexpired vs Google/Microsoft owning refresh; alias vs routes; TOKEN commit vs later import rollback; ASGI disconnect vs abrupt provider EOF; orderly short-CL+close_notify vs abrupt TLS.
- Expected UNKNOWN cases must still prove declared fixture resource disposition.

**Do not authorize by this card:**
- Execution, Docker run, live sockets, PKI generation outside reviewed disposable recipe, real providers/credentials, installation/build, endpoint binding.
- Final framing/port **assembly/merge** (selection JSON 85714151… is data-only: 229 unchanged / 5 deltas / 13 critical entry unchanged; no assembly written).
- Inferring merge authority from framing-fake-v4 one-shot PASS.
- URL rewrite; root; default namespace/sysctl/capability grants; published-port translation; ambient secrets.
- 76-run Cartesian expansion; 57-case native framing repetition; PASS claims.
- Mounting Docker socket or granting Docker daemon access to the runner.
- Quietly granting fault-path owned-resource retirement or automatic failure container disposal (those require explicit later launch-card text).
- Application source edits in the 3-file covering lane (consume final assembled tree only after that tree is separately authorized).

**If final framing/port assembly is later included in a different card:** that card must spell exact file selection/deltas and authority explicitly (the five delta paths + 229 unchanged + 13 critical unchanged from Final-Assembly-Proposed-Source-Selection.json); this preparation card does not supply that authority.

**Flags after a future approval of this card alone:**
- implementation_authorized=true for listed fixture/packet authoring only
- launch_authorized=false
- xecuted=false
- prep_is_not_pass=true
- endpoint unbound

**Still required before any launch:** port-zero authorized result (still open); final assembled application hashes; topology bind outcome recorded (unchanged-isolation attempt first); separately frozen command/hash/bounds launch packet(s); any fault-retirement/container-disposal bits explicitly listed.

**Proposal pins:** Implementation-Scope-Proposal.md + Case-Registry.md (hashes on ARTIFACT-HASHES / TIP-FREEZE when frozen).
