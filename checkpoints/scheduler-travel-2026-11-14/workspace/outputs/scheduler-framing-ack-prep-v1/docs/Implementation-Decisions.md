# Framing-ack implementation decisions (Jim/Justin)

executed=false; launch_authorized=false; endpoint=unbound. Prep is NOT a PASS.

## Application
- covering_http_transport.py: covering-local `_GuardedHTTPResponse` + before-decode `_admit_framing_headers` / `_admit_fixed_length_complete`. Retains 8192 collection loop.
- covering_joined_https.py: exact `suppress_ragged_eofs=False` at covering-only wrap_socket (prospective 76017776…).
- covering_provider_context.py: UNCHANGED (route fix preserved).
- Private parser coupling disclosed to host http.client 3A752927… and captured native C2C06941…; requalify on upgrade.

## Dex provisional review P1–P3 (87E24D1A…) — addressed before freeze
- P1: `_read_and_discard_trailer` retains `trailers_read > http.client._MAXHEADERS` AND requires final `\r\n`. Witnesses: C-TRAILER-COUNT-100 / C-TRAILER-COUNT-101.
- P2: `_read_next_chunk_size` admits only unsigned hex (`_CHUNK_SIZE_HEX`) before return; refuses signed/negative before any inherited `_safe_read`/`fp.read(-1)`. Witness: C-NEG-SIZE with `negative_receive_requested=false`.
- P3: TE gate uses `raw_te.lower() == "chunked"` with NO strip (matches begin()); refuses whitespace-padded TE (H-TE-WS-LEAD/TRAIL). CL uses SP/HTAB-only `_ows_strip` then unsigned decimal. Coherence check: TE accepted ⇒ `response.chunked` true.

## Header compatibility = REVIEW CANDIDATE (not accepted contract)
See EXPECTED.json `changed_accepted_refused_spellings` and policy_pending labels on oracles.

## Verification
- Four roles only. Reuse 57 T05 wires + RESULT D29D4CFD… as immutable original evidence.
- Added: H-DEFECT-COLONLESS; P1/P2/P3 witnesses; TLS option forward; cleanup C-R02..C-R06 lineage; item/byte excess; primary+both closes; OAuth UNKNOWN retirement.
- Limits proposal: 30+5+5+5=45s; 64KiB/stream; 256KiB result; 2 readers; STOP/no-overwrite/UNKNOWN/no-retry; outer exclusions disclosed.

## Blockers / qualifications
- Material header-policy freeze still Trish's before contract/launch.
- Native orderly vs abrupt TLS EOF unproved (byte fakes ≠ close_notify).
- Host characterization ≠ native runtime proof.
- staged B04B3D6B superseded by 29CBD53C after P1–P3.