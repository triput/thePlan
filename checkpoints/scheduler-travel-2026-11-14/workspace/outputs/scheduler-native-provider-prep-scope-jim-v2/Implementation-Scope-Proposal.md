# Native synthetic-provider packet — implementation-scope proposal v2 (documents only)

Jim → Dex, 2026-11-12. Documents-only successor revision addressing Dex R1–R8. **Proposal only.**

Preserves immutable jim-v1: TIP on-disk 531BFBDE267872AFA3DC58C0294ECFE3270F01650D5DA52D5D1F900A5A45C130 / tip_sha256 2ED4F5DC6E97B54DAF6F06D51DD47975B7D3861241F453CEC4CBB54625958BDA / Proposal 126AC17B31B14C3D2AF5864ABB9830666A42F6C7A2F453F152521AF52431555C.

Dex review pin: Dex-Review-and-Revision-Scope.md SHA256 5306D7C646A26080F1AD4C3CA1687409E14F20312A41A1F5C6889345A0FB9059.

| Flag | Value |
| --- | --- |
| xecuted | alse |
| launch_authorized | alse |
| implementation_authorized | alse |
| prep_is_not_pass | 	rue |
| endpoint | unbound |
| Slack tip from this seat | none |

Canonical case inventory: Case-Registry.md in this packet. **Native STOP count = 27** (+ 4 pure CF witnesses). All **76** planning IDs retained.

No fixture/impl/source authoring, imports/tests, PKI, sockets, Docker, install, merge, or execution by this packet.

---

## 0. Hash-pinned inputs

| Artifact | SHA256 |
| --- | --- |
| Dex-Review-and-Revision-Scope.md (R1–R8) | 5306D7C646A26080F1AD4C3CA1687409E14F20312A41A1F5C6889345A0FB9059 |
| jim-v1 TIP-FREEZE.json (immutable) | 531BFBDE267872AFA3DC58C0294ECFE3270F01650D5DA52D5D1F900A5A45C130 |
| jim-v1 Implementation-Scope-Proposal.md | 126AC17B31B14C3D2AF5864ABB9830666A42F6C7A2F453F152521AF52431555C |
| Jim-Native-Provider-Preparation-Scope-Assignment.md | 6800E75B876D549CD1468B8E6B93D2F04EF36C986AC650D45C5A0EDB7F728113 |
| Scheduler-Consolidated-Plan-Current.md (current) | 2575E3F8EEC395E45707F07819092D58E249D1406A2D840AB53FECC928CD6637 |
| Next-Native-Provider-Slice-Seams-and-Gaps.md | 9EA98B204C42F827914192697C0E421AAAF6E1E87DA9164B4077E7ABE1BDAE74 |
| Native-OAuth-Owning-Terminal-Evidence-Seams.md | C331BDACD0FF1435673CD9B393752A7A3AE41A75229B1422BFE1EC7F9CC609CA |
| Native-OAuth-Owning-Terminal-Source-Pins.json | 2CBBD0B6CB50CABE680732FF3E6F88C7AC5FFDDB2B9FBF2D0D08DD9EB9634AE8 |
| Transport-Deadline-Suite-Budget-Review.md | 2DC649FAC1CA87E5F04AFFFE65DF74F178B7524E2C0A9616920B2A79818696D4 |
| Transport-Completion-Audit-Current.json (current; 76 IDs) | 476BA8245705BB2FDAC2F892CB65DCDACA5C7B86A742ADD7A1C8CDA01B0852CA |
| Transport-Property-Evidence-Reuse-Overlay.json | D27CA2442CEDAF6EB045C50BE6F2A9C205EA00A8EC6DB595832F583910CCA57A |
| T01-Route-Property-Evidence-Reuse.json | 5CD74FD03464C016466B525C14CE3AC92E8B58A460602F406D94E5106275C5A3 |
| Retirement-Statement-Lineage-Reuse.json | EF213E03F7D37705C8954BFA2F7912E73303B08C2B6E80D30C736F3CDA580FE3 |
| Scheduler-Private-Beta-Finish-Line-Working.md | 80FE8308B4D06B0D8F2D50067DBCDFB1336077E917510929946B33075A2D75EC |
| Header-Compatibility-Decision-For-Review.md | AEAE53432BDCCA6BB805E7EC5B4A2F7AA37370B2C358F5E7D8738A165F81A1D0 |
| Trish-Header-Policy-Approval.json | 1C932F1A569AD55DF9B86C8994946B052B5BCDDB21676B848EC7ACBF98464059 |
| Final-Assembly-Proposed-Source-Selection.json (data-only) | 857141512AADF6F90F1CA8F92547A777E3D5FE943671495512FA18CEA7CBA296 |
| Framing FAKE-FRAMING-ACK-RESULT.json | 3905A070AE06EF2EA6B31C8A8D1407A6F58E46B549E1118FF3928C00866ECBA3 |
| Framing FAKE-FRAMING-ACK-LAUNCH-RECEIPT.json | 166BB080CCCD19B80F88703BA3CC16B46142DAEF3904BDAF5D7AA9CF3254E6E6 |
| Framing Dex-Run-Reconciliation.json | E9BCFB2D91A4C6E52657DF719F749B0FE8E21959D9CBEDB074516CB729C50E18 |
| D2 FAKE-D2-RESULT.json | 2FB80F2C50BBC1302EA71728EC899EAD665660D69B6CE970FF13D10791BF3CCD |
| D2 FAKE-D2-LAUNCH-RECEIPT.json | 9E11B3A1F91186AEA945B4FF828B63A732A8A99228DEB765AA08C4E50FBAB91D |

### 0.1 Retained production / OAuth pins (unchanged intent from v1)

Eight OAuth owning-terminal source pins and release-plan / JoinedTLS / budget pins from jim-v1 §0.1–0.2 remain cited. Production **JoinedTLS default** (no unnecessary injection seam). Distinct Google/Microsoft owning refresh. Token/import terminal separation. Vendor URL + numeric 127.0.0.1 dial + verify-full. tmpfs private keys. Full accepted inventory + property-matched reuse.

Prospective JoinedTLS EOF candidate bytes 760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427 remain candidate-only until final assembly is authorized. Final assembled application source is **not** frozen here.

### 0.2 Framing-fake-v4 actual run fact (updates D1; not native authority)

Trish authorized exactly one framing verification (call_5d9900df08de4a0ca4c63bb8742cb313). Ran once; child PID 202980 exit 0; **73/73** exact controls matched.

- RESULT 3905A070AE06EF2EA6B31C8A8D1407A6F58E46B549E1118FF3928C00866ECBA3
- Receipt 166BB080CCCD19B80F88703BA3CC16B46142DAEF3904BDAF5D7AA9CF3254E6E6
- Both readers joined EOF; 0 stdout/stderr; 537 input / 21 partial runtime postpins unchanged
- Exact observations: EXCESS-ITEM-BYTE → OBSERVED_REFUSE / CoveringTransportRefused (item+byte); PRIMARY-BOTH-CLOSES → OBSERVED_UNKNOWN with FakeResponseCloseError + FakeTransportCloseError at **host-fake** scope
- **Do not promote to native TLS / owning-call proof.** Port verification still unapproved/unexecuted.

---

## 1. Prospective files, roles, lineage (R5 / R8)

### 1.1 Packet root (prospective)

outputs/scheduler-native-provider-v1/ (name frozen at preparation; not created by this proposal).

### 1.2 Host operator / Docker transport / immutable helpers vs in-runner roles

**Host-only (Docker/transport/operator — never inside runner; never mount Docker socket / grant daemon to runner):**

| Role | Lineage | Responsibility |
| --- | --- | --- |
| Operator entry | I01 pattern Invoke-Native.ps1 308D1A816B2D198131E00CB9847EE4C1CD95F2B8E1390CE288602EC155154CC6 → prospective Invoke-Native-Provider.ps1 (fresh copy on later card) | Hash-gate interpreter/Docker/config/manifest; invoke host supervisor once; no retry |
| Host Docker transport | I01 launch-config.json Docker endpoint/pins pattern (
pipe:////./pipe/dockerDesktopLinuxEngine; docker.exe pin lineage) | Create/dispose disposable DB+runner containers; mounts; capture; SIGINT/removal gated per §4 |
| Host supervisor module | I01 supervisor.py A72721BD1E092863B89C77F1FE4C98243759AF9764F9CB8BB31B6402FEBC40DB → prospective ixture/np_supervisor.py **host-side** | Serial batch admission, exact-ID success cleanup authority, STOP on fail; owns container lifecycle API calls on host |
| Immutable helper copies (reuse unchanged where suitable) | I01 ootstrap-postgres-tls.sh, DB image/bootstrap patterns, runner image/runtime pin pattern | Reuse; do **not** create a gratuitous parallel DB/bootstrap stack |
| PKI recipe (fixture-only; unexecuted here) | I01 prepare-c06-runner-tls.sh F1868F913BFBA3841331B397242566938DAF7C2047CACDD5031611B62D60E6DA → prospective prepare-np-provider-tls.sh | New vendor SANs; tmpfs private keys; wrong-CA/wrong-name distinct material |

**In-runner (no Docker ownership):**

| Path under packet payload/ | Role | Lineage |
| --- | --- | --- |
| ixture/np_integrated_runner.py | **Suite registry/guard only**: loopback-only namespace check, nonroot/runtime/CA/inventory admission, serial case invoke, join checks. **Does not** create containers, mount Docker socket, or call the Docker daemon. | I01 integrated_runner.py E77B3D09AA1907527516118659032C2352807DAFB8F3FBE419A44915ABCAB35A (corrects v1 mis-assignment of DB/runner creation to this module) |
| ixture/np_runner_entry.py | In-runner entry: imports suite, binds disposable settings, typed receipt | I01 
unner_entry.py 2A4602CCDFA68787697ED4FD472B3BEA41FD9FC31F8F808C409339140C81FA3E |
| ixture/np_suite.py | Finite case inventory from Case-Registry.md §A/§B | new mutable |
| ixture/np_receipts.py | Oracles; sanitized booleans/hashes; no secrets/raw bodies | new mutable |
| ixture/np_provider_peer.py | Synthetic HTTPS peer (fixture-only) | new mutable |
| ixture/np_provider_transcript.py | Finite Host/path/method exchange script | new mutable |
| ixture/np_provider_routes.py | Reviewed HTTPSPeer table: vendor host/port unchanged; numeric loopback dial; fixture CA | new mutable |
| ixture/np_auth_seed.py | Disposable account seed; plan-clock capture/check (ATTEMPT_VALIDITY_SECONDS=600 pattern) | I01 i01_auth_seed.py F66B4FE3D13F47122754835D3AF45EE6770D45B4D7250D35B013F026C4CC4371 |
| ixture/np_alias_seed.py | Microsoft primary alias seed for live identity evidence | new mutable |
| launch-config.json / 
unner-config.json | Exact commands/hashes/limits — **frozen only on later launch card** | scaffolds unlaunched |

New native fixture roles are **outside** the current 3-file / 4-fake-role authoring lane. No code until a later concrete Trish card names fresh-copy roles + routine same-contract corrections (R8).

### 1.3 Genuine production seams (retained)

| Seam | Decision |
| --- | --- |
| JoinedTLS factory | **None new.** Release plan default; leave alias unwrapped. |
| Provider routes | Fixture HTTPSPeer entries only |
| Auth / OAuth settings | Fixture synthetic seed; no ambient secrets |
| Alias → canonical calendar ID | Seed + observe existing canonicalize behavior |
| Token terminal | Existing native TOKEN hook; observe |
| TLS EOF option | Lands only via authorized framing/final assembly — not this proposal |
| Port-zero policy | Separate packet; unexecuted |

### 1.4 Case ↔ evidence

See **Case-Registry.md** — single exact list + exact requirement map. No duplicate competing registries.

---

## 2. Coherent native vertical demonstration (retained)

One synthetic **Microsoft** target drives the primary vertical:

1. Production in-process HTTP ingress → dispatch → role connector
2. CoveringReleasePlan.for_request → CoveringHTTP with **default JoinedTLS** (alias unwrapped)
3. Reviewed HTTPSPeer: vendor URL host/port unchanged; dial 127.0.0.1:443; server_hostname = vendor hostname; fixture CA; CERT_REQUIRED / verify-full
4. Synthetic provider TLS peer; finite transcript
5. Native ORM token + event-import units with real TOKEN terminal acknowledgments
6. Final persisted assessment inputs **change** as a consequence of observed coverage

Google appears as **separate owning refresh cases**, not a second full vertical duplicate.

Distinctions retained: nonexpired ≠ OAuth success; Google ≠ Microsoft; alias canonicalization ≠ route configuration; TOKEN COMMIT survives later import rollback; truncated/lost ack → UNKNOWN without claiming provider non-rotation from unchanged locals.

---

## 3. Topology, trust, close modes (R1)

### 3.1 Declared topology

| Element | Value |
| --- | --- |
| URL origin/port | Unchanged vendor |
| Dial | Numeric 127.0.0.1:443 inside isolated fixture network namespace |
| TLS | verify-full; server_hostname = vendor hostname; fixture CA |
| DNS/public | Do not resolve/contact public addresses |
| Listener | Runner-owned loopback:443 TLS peer (fixture) serving finite transcript |
| DB | Separate container/trust; provider private keys never in DB trust store |

### 3.2 Nonroot :443 — initial attempt vs contingencies

**Initial attempt (default):** use the **existing unchanged isolation** as the first nonroot :443 bind attempt. Include a **bounded bind probe** in the later reviewed launch. If unsupported → **STOP honestly** (non-PASS). No silent fallback.

**Do not default** to namespace port setting / sysctl / capability grants before observing need. Those are **consequential contingency proposals only**, not present preparation/execution authority:

| Contingency | Description | When discussable |
| --- | --- | --- |
| A | Namespace-local unprivileged-port setting permitting nonroot :443 inside that namespace only | Only after unchanged-isolation bind fails and Trish reviews |
| B | Narrow CAP_NET_BIND_SERVICE on disposable runner only | Same — higher privilege cost |
| C | High-port peer + matching high-port peer.port | **Cannot** claim unchanged full vendor-origin composition; separately labeled if ever used |
| D | STOP at bind failure | Honest default behavior on initial attempt failure |

**Forbidden now and as silent fallback:** root, published-port translation, URL rewrite.

### 3.3 Orderly vs abrupt + failure-stage counters

Retained from v1: orderly close_notify vs abrupt truncation; stall stage counters (pre_accept … post_body); TCP refusal = no accept. Native framing requal on orderly path uses valid JSON prefix + short Content-Length + orderly TLS close so SSL abrupt-EOF does not mask HTTP completeness (R7).

---

## 4. Clocks, batches, budgets, plan validity (R4)

### 4.1 Production timing (where claimed)

From covering_request_budget.py D5C465CC…:

- Work deadline: start + **210s**
- Request deadline: start + **240s**
- Cumulative cleanup allowance: **30s** shared

Supervisor timeout ≠ application expiry.

### 4.2 Stall arithmetic (corrected)

Three independent full work-expiry witnesses reserve **630s** of configured **work** windows (3×210). Conservatively allocating **240s/request** reserves **720s** of request envelopes including cleanup headroom. That is **not** evidence of a minimum **720s elapsed stall**. Keep max **240/request** + shared **30** cleanup where claimed.

### 4.3 Inherited 600s seed/plan validity

From I01 i01_auth_seed.py F66B4FE3…: ATTEMPT_VALIDITY_SECONDS = 600; capture_plan_instant() / ssert_plan_still_valid(t_plan).

**Rules for this suite:**

1. Capture T_plan at case/attempt admission (state explicitly in receipts).
2. Check plan validity at seed boundaries and before each seeded case proceeds.
3. Use **fresh planning** for each distinct predeclared case/attempt, **or** split batches so 600s validity cannot defeat a valid test.
4. **Never** reseed/retry the same failed or expired attempt.
5. Three full stalls cannot share one 600s plan horizon without fresh per-case planning or separate launches.

Do **not** copy I01 
unner_seconds=600 / suite_seconds=900 or the 64-command cap as authority without accounting against the canonical 27(+4) list.

### 4.4 Finite serial batches (computed from registry)

| Batch | Cases | Floor notes |
| --- | --- | --- |
| B0 CF witnesses (optional separate) | NP-T01-*-CF ×4 | Short; no 240s stall |
| B1 Vertical-OAuth | NP-V-* + NP-T06-* non-stall (12) | Mostly short; refresh/import/assessment; fresh T_plan per seeded case |
| B2 TLS trust | T03 VALID/WRONG-CA/WRONG-NAME/TCP-REFUSAL (4) | No full 240s stall |
| B3 Full stalls | HANDSHAKE/HEADER/BODY stall (3) | Prefer **three separately authorized one-shots** or one runner with **per-case fresh T_plan**; each case ≤240s request claim + shared 30s cleanup envelope accounting |
| B4 Timing remainder | PARTIAL-SEND, DEADLINE, DISCONNECT (3) | Isolate DEADLINE if near full window |
| B5 Closure + retirement + thread | T05×2, T07×2, T08 (5) | Real close_notify; owned retirement |

**Jim recommendation:** separately authorized serial one-shot launches per batch (and per stall case if plan-validity / STOP isolation prefers). Avoid one mega-suite.

### 4.5 Computed caps (freeze on later launch cards only)

Derive command_count_cap, runner/suite seconds, PKI/retirement budgets from the actual 27(+4) list + production 210/240/30 + host setup overhead disclosed separately. Excluded from app-deadline proof: host Docker I/O, image pull, unrelated OS scheduling, file hashing, CLI capture drain.

Proposed starting points (not copied as blind authority): per-case app request max 240s when claiming production deadline; shared cleanup 30s; output capture ≤1 MiB public; command cap sized to batch (I01 used 64 — re-account per batch).

---

## 5. Retirement authority (R6)

Distinguish:

| Kind | Meaning | Authority now |
| --- | --- | --- |
| Declared owned-resource retirement | Joined bounded retirement of owned peer worker / PKI-child / reader within cleanup allowance | Design intent for success path; **later launch may explicitly request** one bounded owned peer/PKI-child/reader retirement attempt on fault (like existing local-child retirement envelope). **Do not quietly grant now.** |
| State-changing container failure disposal | Docker container removal / SIGINT on failed runs | **Separately gated**; not implied by owned-resource retirement language |
| Unconfirmed / unjoined retirement | Join/confirm missing | **STOP / UNKNOWN** |
| Foreign-owner cleanup / force / retry | Forbidden | Never |

Expected application UNKNOWN cases must still prove **declared fixture resource disposition** (owned resources accounted; no silent leak claim).

Success path: exact-ID stop + join within cleanup allowance (I01 pattern). Failure path: no automatic container disposal unless the reviewed launch card explicitly includes it.

---

## 6. Fault stimuli exactness (R7)

| Case | First guard / input channel | Must not conflate with |
| --- | --- | --- |
| NP-T04-DISCONNECT | ASGI/request-disconnect + joined worker/provider retirement | Abrupt provider TLS EOF |
| NP-T05-ABRUPT-TRUNCATION | Abrupt TLS truncate without close_notify | Malformed JSON / chunk / header; ASGI disconnect |
| NP-T05-ORDERLY-CLOSE | Valid JSON prefix + short Content-Length + orderly TLS close_notify | Abrupt EOF masking incompleteness |
| NP-T06-MALFORMED-ACK | Malformed OAuth ack after send | Truncated ack; partial send; lost ack |
| NP-T06-TRUNCATED-ACK | Truncated ack | Malformed; abrupt TLS alone |
| NP-T06-PARTIAL | OAuth partial send | Lost ack; ASGI disconnect |

Share one case only when the **same exact observation** proves both IDs. Disclose private parser coupling. No 57-case native repetition.

---

## 7. Final assembly dependency (R8) — data-only citation

Final-Assembly-Proposed-Source-Selection.json 857141512AADF6F90F1CA8F92547A777E3D5FE943671495512FA18CEA7CBA296:

- **229** unchanged from passed native
- **5** deltas: covering_http_transport.py 29CBD53C…, covering_joined_https.py 76017776…, covering_provider_context.py 65529CBC…, covering_refresh_import.py 84F50367…, covering_transport_policy.py 5F48FD7E… (port candidate)
- **13** critical entry paths unchanged (release plan, role connector/admission, request budget, native terminal/ORM/checkout, domain dispatch/adapters, HTTP dispatch, ingress, target transaction, refresh locks, …)
- **pp_files_written: false** — no assembly written
- Do **not** infer merge authority from framing one-shot fake PASS or from this JSON alone

Native launch commands/hashes = **later gated freeze**.

---

## 8. Trish source-preparation card wording + open decisions

See Trish-source-preparation-card-wording.md and Decisions-and-Open-Questions.md.

**Authoring boundary:** new np_* roles outside current lane; later Trish card may cover named fresh-copy roles + routine same-contract corrections; **no code until approved**.

---

## 9. Handback summary

- Documents-only v2 successor; v1 immutable hashes preserved.
- R1–R8 addressed; disposition matrix in packet.
- Canonical native cases **27** (+4 CF); 76 IDs mapped without orphans.
- Host Docker ≠ in-runner 
p_integrated_runner.
- Framing D1 updated to PASS 73/73 host-fake; not native proof; port still HOLD.
- Clocks: 630s work / 720s request-envelope accounting corrected; 600s plan validity explicit.
- Prep ≠ pass; endpoint unbound; no Slack tip.

— Jim
