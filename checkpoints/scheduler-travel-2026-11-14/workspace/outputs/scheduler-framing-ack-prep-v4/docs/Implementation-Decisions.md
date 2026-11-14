# Framing-ack implementation decisions (Jim/Justin) — prep v4

executed=false; launch_authorized=false; endpoint=unbound. Prep is NOT a PASS.

Successor of prep v3 (immutable TIP `BD52764433172FD2FA54938C8DCA4C142C2E626DB6723AE095C2B02621773209`) under Dex provisional checker finding p1794461191 on tipped check `9F2DFB45D1EF358E16CC94481180F89D7CECB44F8DE4A2F940D3FEE105FB0698`. Immutable v1 TIP `FA211E1D1BFB6C72FF070A7B211E4D80CCA7EDC78E0F6BE3B5969FDF0810DFF4` / v2 TIP `569CA4F5C97A947F391F2AF3C616C3581851ED2853E1E6F2E9AEF80FFE2E5697` / v3 TIP `BD52764433172FD2FA54938C8DCA4C142C2E626DB6723AE095C2B02621773209` preserved (not rewritten).

## Application
- covering_http_transport.py: covering-local `_GuardedHTTPResponse` + before-decode `_admit_framing_headers` / `_admit_fixed_length_complete`. Retains 8192 collection loop.
- covering_joined_https.py: exact `suppress_ragged_eofs=False` at covering-only wrap_socket (prospective 76017776…).
- covering_provider_context.py: UNCHANGED (route fix preserved).
- Candidate HTTP hash **retained** from v1/v2/v3: `29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368`.
- Candidate TLS hash **retained**: `760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427`.
- Private parser coupling disclosed to host http.client 3A752927… and captured native C2C06941…; requalify on upgrade.
- Port-zero packet **not** merged; `covering_transport_policy.py` A265F81F… UNCHANGED.
- **No application change in v4.**

## Header compatibility — APPROVED (cite, not policy-pending)
- Decision: `Header-Compatibility-Decision-For-Review.md` SHA256 `AEAE53432BDCCA6BB805E7EC5B4A2F7AA37370B2C358F5E7D8738A165F81A1D0`
- Approval: `Trish-Header-Policy-Approval.json` SHA256 `1C932F1A569AD55DF9B86C8994946B052B5BCDDB21676B848EC7ACBF98464059`
- Contract labels cite the above. Leading-wire TE OWS → parser-visible `chunked` → **pass** (`H-TE-WS-LEAD`). Trailing TE OWS remains parser-visible → **refuse** (`H-TE-WS-TRAIL`). Valid ordinary positives retained. No new trailer/extension grammar beyond stated checks. OAuth UNKNOWN/counter/retirement contracts preserved.
- `policy_pending` on oracle candidate observations remains **false** under the approved policy (semantic refuse/accept outcomes unchanged).

## Dex provisional checker finding (p1794461191) — addressed in v4
- **Finding:** `assert_match` flat candidate-field whitelist included `policy_pending`. Wire path calls `assert_match(cid+"/candidate", cand, row["candidate"])` **before** `emit_wire_candidate`. `run_http_catch` cand has no `policy_pending` key; EXPECTED candidate metadata has `policy_pending=false` → `observed.get("policy_pending")` is None vs False → WitnessFailure before result completes.
- **Fix (check only):** exclude `policy_pending` from `assert_match` flat runtime observation whitelist. Keep accepted-policy label as explicitly frozen **metadata** on EXPECTED rows; `emit_wire_candidate` still stamps it into launcher output from the row (exact launcher schema preserved). Do **not** assert that metadata against measured cand. Strict assertions retained on real outcome/exception/close counters and all other actual witnesses. No broad skip of missing observed fields; mismatches still FAIL.

## Dex REVISE (AEF66204…) — carried forward from v3
1. **Outer admission noncircular chain** — regenerate OUTER subjects + PACKET-SHA256SUMS after final code/data freeze (EXPECTED unchanged; check/PACKET/OUTER updated). Preserve v1/v2/v3 tipped packets.
2. **Exact result oracle schema** — every EXPECTED.inputs row has top-level `predicted_outcome: "PASS"` + nonempty top-level `exact_predicate` (unchanged from v3; EXPECTED hash retained `08C2367D886205C33100C8BEC6C95E5502D7AA75622B4145D77D076960F9FEA2`).
3. **CALLER proof labels** — `direct_http_replay_plus_matched_immutable_original_caller_evidence`; owning-caller obligation preserved/unproved in-candidate.
4. **Concrete Commands-Held** — exact wrapper/admission hashes after freeze (held; not invoked).

## Dex provisional reviews (carried)
### Review-1 (87E24D1A…) — P1–P3 gate — addressed in v1 candidate (retained)
### Review-2 (4BA86BAB…) — OWS wire-oracle truth — retained from v2

## Verification
- Four roles only. Reuse 57 T05 wires + RESULT D29D4CFD… as immutable original evidence.
- Result dialect: top-level `PASS` + nested `OBSERVED_*` (aligned to `validate_result_file` + check emission).
- Limits proposal: 30+5+5+5=45s; 64KiB/stream; 256KiB result; 2 readers; STOP/no-overwrite/UNKNOWN/no-retry; outer exclusions disclosed.

## Independent static note — port-zero (NO implementation authority)
Unchanged from v2/v3. Outside lane; no edit applied. See `docs/Port-Zero-Static-Source-Note.md`.

## Blockers / qualifications
- Native orderly vs abrupt TLS EOF unproved (byte fakes ≠ close_notify).
- Host characterization ≠ native runtime proof.
- Port-zero fix awaits Trish preparation-extension approval; outside this framing lane.
- Owning-caller proof obligation remains (CALLER rows are direct HTTP replay only).
- Immutable v1 TIP `FA211E1D1BFB6C72FF070A7B211E4D80CCA7EDC78E0F6BE3B5969FDF0810DFF4` / v2 TIP `569CA4F5C97A947F391F2AF3C616C3581851ED2853E1E6F2E9AEF80FFE2E5697` / v3 TIP `BD52764433172FD2FA54938C8DCA4C142C2E626DB6723AE095C2B02621773209` / candidate `29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368` preserved (not rewritten).
- Prep is not PASS; no execute/import/compile/helper invocation performed in authoring.
