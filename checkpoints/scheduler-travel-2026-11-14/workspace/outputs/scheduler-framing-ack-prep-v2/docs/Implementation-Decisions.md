# Framing-ack implementation decisions (Jim/Justin) — prep v2

executed=false; launch_authorized=false; endpoint=unbound. Prep is NOT a PASS.

## Application
- covering_http_transport.py: covering-local `_GuardedHTTPResponse` + before-decode `_admit_framing_headers` / `_admit_fixed_length_complete`. Retains 8192 collection loop.
- covering_joined_https.py: exact `suppress_ragged_eofs=False` at covering-only wrap_socket (prospective 76017776…).
- covering_provider_context.py: UNCHANGED (route fix preserved).
- Candidate HTTP hash **retained** from v1: `29CBD53C85E8D40185A5E7DF73DF85B752A34837D25FCD65DB6504AFB775B368` (gate already matched begin()/chunked; Review-2 required oracle/docs truth, not app edit).
- Private parser coupling disclosed to host http.client 3A752927… and captured native C2C06941…; requalify on upgrade.

## Dex provisional reviews
### Review-1 (87E24D1A…) — P1–P3 gate — addressed in v1 candidate
- P1: `_read_and_discard_trailer` retains `trailers_read > http.client._MAXHEADERS` AND requires final `\r\n`. Witnesses: C-TRAILER-COUNT-100 / C-TRAILER-COUNT-101.
- P2: `_read_next_chunk_size` admits only unsigned hex (`_CHUNK_SIZE_HEX`) before return; refuses signed/negative before any inherited `_safe_read`/`fp.read(-1)`. Witness: C-NEG-SIZE with `negative_receive_requested=false`.
- P3 gate: TE uses `raw_te.lower() == "chunked"` with NO strip (matches begin()); CL uses SP/HTAB-only `_ows_strip` then unsigned decimal. Coherence: TE accepted ⇒ `response.chunked` true.

### Review-2 (4BA86BAB…) — OWS wire-oracle truth — addressed in prep v2 (docs/oracles only)
- `Message.get_all` returns **parser-visible** values, not literal wire bytes after the colon.
- Host `email._policybase.Compat32.header_source_parse` (lines 293–303) **lstrips leading SP/HTAB** after the colon and rstrips CR/LF.
- Therefore **actual wire** `Transfer-Encoding:` + leading field OWS + `chunked` becomes parser value `"chunked"` and is a **chunked positive / PASS** under the existing gate (`H-TE-WS-LEAD`).
- **Trailing** OWS stays parser-visible (`"chunked "`) and **REFUSES** (`H-TE-WS-TRAIL`).
- Helper-injected `Message(' chunked')` ≠ wire outcome; do not use helper metadata as wire-spelling proof. Use actual HTTPResponse parsing path for claimed wire spellings. No raw-header interception.

v1 claims that both `H-TE-WS-*` refused were incorrect for LEAD on the real wire path; corrected here.

## Header compatibility = REVIEW CANDIDATE (not accepted contract)
See EXPECTED.json `changed_accepted_refused_spellings` and policy_pending labels on oracles.

## Verification
- Four roles only. Reuse 57 T05 wires + RESULT D29D4CFD… as immutable original evidence.
- Added: H-DEFECT-COLONLESS; P1/P2/P3 witnesses; TLS option forward; cleanup C-R02..C-R06 lineage; item/byte excess; primary+both closes; OAuth UNKNOWN retirement.
- Limits proposal: 30+5+5+5=45s; 64KiB/stream; 256KiB result; 2 readers; STOP/no-overwrite/UNKNOWN/no-retry; outer exclusions disclosed.

## Independent static note — port-zero origin check (NO implementation authority)
Attributed Dex offline finding; preparation-extension card pending. **Not** in the approved three-file lane. **No edit** to `covering_transport_policy.py`; **no** port-zero controls added in this prep.

- Read/hash-verified: `scheduler-port-zero-proposal-v1/Preparation-Scope-For-Approval.md` SHA256 `A27E47A5B7106708CC1A6E683D645CAB2821FBA1FAE2F45E7A7488F1DB5B0F85`
- Read/hash-verified: `scheduler-port-zero-proposal-v1/Proposed-Fix.diff` SHA256 `C69EB5EFFAD47FBC1BB2A085DCF7620D736EF713BC09B4D4984736104BC9F8CB`
- Finding: `HTTPSPeer.check_url` uses `(u.port or 443)`; `urllib.parse` port may be `int(0)`, so URL `:0` can pass a peer-443 origin check via truthiness fallback. Dial still uses pinned destination — exact-origin admission mismatch, not arbitrary-destination proof.
- Narrow proposed (not applied): `(443 if u.port is None else u.port)`.
- Packet candidate policy file hash (unchanged, not edited): `A265F81F72E719B23FE3DE9BF332E2DE01D8E90073F3AC04675EC6A4B2203598`.

## Blockers / qualifications
- Material header-policy freeze still Trish's before contract/launch.
- Native orderly vs abrupt TLS EOF unproved (byte fakes ≠ close_notify).
- Host characterization ≠ native runtime proof.
- staged B04B3D6B superseded by 29CBD53C after P1–P3 (v1); v2 retains 29CBD53C.
- Port-zero fix awaits Trish preparation-extension approval; outside this framing lane.
- Immutable v1 TIP `FA211E1D…` / candidate `29CBD53C…` preserved (not rewritten).
