# Framing-ack implementation decisions (Jim/Justin) — prep v3

executed=false; launch_authorized=false; endpoint=unbound. Prep is NOT a PASS.

Successor of prep v2 (immutable TIP `569CA4F5…`) under Dex REVISE audit `AEF66204…` (p1794459957). Immutable v1 TIP `FA211E1D…` also preserved (not rewritten).

## Application
- covering_http_transport.py: covering-local `_GuardedHTTPResponse` + before-decode `_admit_framing_headers` / `_admit_fixed_length_complete`. Retains 8192 collection loop.
- covering_joined_https.py: exact `suppress_ragged_eofs=False` at covering-only wrap_socket (prospective 76017776…).
- covering_provider_context.py: UNCHANGED (route fix preserved).
- Candidate HTTP hash **retained** from v1/v2: `29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368`.
- Candidate TLS hash **retained**: `760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427`.
- Private parser coupling disclosed to host http.client 3A752927… and captured native C2C06941…; requalify on upgrade.
- Port-zero packet **not** merged; `covering_transport_policy.py` A265F81F… UNCHANGED.

## Header compatibility — APPROVED (cite, not policy-pending)
- Decision: `Header-Compatibility-Decision-For-Review.md` SHA256 `AEAE53432BDCCA6BB805E7EC5B4A2F7AA37370B2C358F5E7D8738A165F81A1D0`
- Approval: `Trish-Header-Policy-Approval.json` SHA256 `1C932F1A569AD55DF9B86C8994946B052B5BCDDB21676B848EC7ACBF98464059`
- Contract labels cite the above. Leading-wire TE OWS → parser-visible `chunked` → **pass** (`H-TE-WS-LEAD`). Trailing TE OWS remains parser-visible → **refuse** (`H-TE-WS-TRAIL`). Valid ordinary positives retained. No new trailer/extension grammar beyond stated checks. OAuth UNKNOWN/counter/retirement contracts preserved.
- `policy_pending` on oracle candidate observations is **false** under the approved policy (semantic refuse/accept outcomes unchanged).

## Dex REVISE (AEF66204…) — addressed in v3
1. **Outer admission noncircular chain** — regenerate OUTER subjects + PACKET-SHA256SUMS + INPUT-MANIFEST consistency after final code/data freeze (EXPECTED/check/etc.). Preserve v1/v2 tipped packets.
2. **Exact result oracle schema** — every EXPECTED.inputs row now has top-level `predicted_outcome: "PASS"` (launcher compares to result `observed_outcome`) and nonempty top-level `exact_predicate` mirroring emitted entry keys. Nested candidate/observation fields retain `OBSERVED_*` dialect. Launcher `validate_result_file` strictness retained (no exit0/wildcard/broad allowed).
3. **CALLER proof labels** — CALLER-* rows use the same direct CoveringHTTP `run_http_catch` path as wire controls (not `_CoveringClient` / `refresh_access_token`). Labeled `direct_http_replay_plus_matched_immutable_original_caller_evidence`; historical T05 originals remain distinct; owning-caller obligation preserved/unproved in-candidate. No new evidence from ID reuse alone.
4. **Concrete Commands-Held** — exact wrapper/admission hashes after freeze (held; not invoked).

## Dex provisional reviews (carried)
### Review-1 (87E24D1A…) — P1–P3 gate — addressed in v1 candidate (retained)
- P1: trailer `_MAXHEADERS` count + final CRLF (C-TRAILER-COUNT-100/101).
- P2: unsigned hex chunk size; C-NEG-SIZE refuse before read(-1).
- P3 gate: TE `raw_te.lower() == "chunked"` with NO strip; CL SP/HTAB-only `_ows_strip`.

### Review-2 (4BA86BAB…) — OWS wire-oracle truth — retained from v2
- Leading wire TE OWS → PASS; trailing → REFUSE. Helper `Message(' chunked')` ≠ wire outcome.

## Verification
- Four roles only. Reuse 57 T05 wires + RESULT D29D4CFD… as immutable original evidence.
- Result dialect: top-level `PASS` + nested `OBSERVED_*` (aligned to `validate_result_file` + check emission).
- Limits proposal: 30+5+5+5=45s; 64KiB/stream; 256KiB result; 2 readers; STOP/no-overwrite/UNKNOWN/no-retry; outer exclusions disclosed.

## Independent static note — port-zero (NO implementation authority)
Unchanged from v2. Outside lane; no edit applied. See `docs/Port-Zero-Static-Source-Note.md`.

## Blockers / qualifications
- Native orderly vs abrupt TLS EOF unproved (byte fakes ≠ close_notify).
- Host characterization ≠ native runtime proof.
- Port-zero fix awaits Trish preparation-extension approval; outside this framing lane.
- Owning-caller proof obligation remains (CALLER rows are direct HTTP replay only).
- Immutable v1 TIP `FA211E1D…` / v2 TIP `569CA4F5…` / candidate `29CBD53C…` preserved (not rewritten).
- Prep is not PASS; no execute/import/compile/helper invocation performed in authoring.
