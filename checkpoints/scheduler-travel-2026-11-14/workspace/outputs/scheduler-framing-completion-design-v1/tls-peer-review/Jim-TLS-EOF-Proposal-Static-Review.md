# Jim TLS-EOF Proposal Static Review v1

**Reviewer:** Justin (for Jim)
**Date:** 2026-11-11
**Assignment:** Documents-only independent review of the narrow TLS EOF proposal. Ordinary reads / SHA256 / UTF-8 doc writes only. No application/checker/fixture edits, imports, compilation, helper invocation, tests, sockets, PKI, Docker, providers, or execution. Endpoint unbound. No Slack tip from this seat — Jim tips after verify. This review is **not** source-authoring authority; Dex transitions explicitly if Trish approves.
**Flags:** `documents_only=true`; `implementation_authorized=false`; `executed=false`; `endpoint=unbound`; `diff_applied=false`
**Disposition:** **QUALIFIED ACCEPT**

Context held (not reopened): route-fake-v1 QUALIFIED ACCEPT reconciled; one-shot card with Trish; no launch inferred. Framing design reconciled; Dex owns mechanism recommendation. Private-beta finish line: prioritize concrete blockers; do not expand protocol hardening.

---

## 1. Exact input pins (verified this seat)

| Role | Path | Expected SHA256 | Observed |
| --- | --- | --- | --- |
| Trace / proposal | `…/scheduler-framing-completion-design-v1/TLS-EOF-Acknowledgment-Trace-and-Proposal.md` | `F5E761F5E41C595D87F47C3F45A2724C740B534AA2487199F8A561EC751F3C48` | match |
| Unapplied one-line diff | `…/Proposed-TLS-EOF-Option.diff` | `E5DA81D57E19A6ED0524100A6D25FE3FE828D706C9D0014BAF8C5B0188AAF670` | match |
| Pins JSON | `…/Proposed-TLS-EOF-Option-Pins.json` | `CE5AB23AEED325E37C1CB33BF3F49231A3D0E67FFF827A71BB35A6F74BB747FE` | match |
| JoinedTLS original (T07 fake-v2 payload) | `…/covering_joined_https.py` | `2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B` | match |
| CoveringHTTP accepted (T07 = T05 pin) | `…/covering_http_transport.py` | `E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD` | match |
| Captured native `ssl.py` | `…/scheduler-t05-native-provenance-dex-v3.evidence/ssl.py.source` | `0061D6EF21088283498491064B79605B5C26C35DFF527AC850A417994D580AD3` | match |
| Captured native `http/client.py` (static context) | `…/http-client.py.source` | `C2C0694155837D72FC710A4138E5D1E53AE1A652B117A2E23A5B1B0DB527A0F9` | match |
| Prospective JoinedTLS (pins claim; in-memory replace only) | *(no candidate written)* | `760177767EA64A6129E788BA7828FBE998522706791E6CFC5DBB9C2D0C013427` | match via UTF-8 LF in-memory substitute of the single `do_handshake_on_connect=False)` site |

Pins JSON fields cross-check: `original_sha256` = JoinedTLS observed; `diff_sha256` = diff observed; `native_ssl_source_sha256` / `native_http_source_sha256` = captured sources observed; `candidate_file_written=false`; `implementation_authorized=false`; `executed=false`; `endpoint=unbound`.

---

## 2. Source-supported suppression chain (verified)

Exact static chain; line cites are against pinned bytes, not executed behavior.

1. **JoinedTLS.open** (`covering_joined_https.py` `2E6A4ABB…`, lines 58–62): `ssl.create_default_context(cafile=…)`, `check_hostname=True`, `verify_mode=CERT_REQUIRED`, then `context.wrap_socket(..., server_hostname=..., do_handshake_on_connect=False)` — **no** `suppress_ragged_eofs` argument.
2. **SSLContext.wrap_socket** (captured `ssl.py.source` `0061D6EF…`, lines 449–460): default `suppress_ragged_eofs=True`; forwards into `sslsocket_class._create(...)`.
3. **SSLSocket._create** (lines 969–1001): stores `self.suppress_ragged_eofs = suppress_ragged_eofs` (default True).
4. **SSLSocket.recv** (lines 1238–1245): when `_sslobj` present, returns `self.read(buflen)`.
5. **SSLSocket.read** (lines 1107–1126): on `SSLError` with `args[0] == SSL_ERROR_EOF` **and** `self.suppress_ragged_eofs`, returns `b''` / `0` instead of raising.
6. **JoinedTLS.receive** (lines 108–118): `data = self.sock.recv(maximum)` after budget/want-IO waits; returns bytes unchanged. Does **not** catch `ssl.SSLError`.
7. **CoveringHTTP** (`E942BB43…`, lines 99–106): `response.read(8192)` until falsy part, then `json.loads(body)`. With neither accepted Content-Length nor completed chunk framing, empty bytes end the body loop. A syntactically complete JSON object is **not** evidence of orderly authenticated TLS end-of-message.

**Verdict:** The proposal’s causal chain is exact and source-supported. It remains a **failure mechanism**, not a reproduced native teardown outcome. OpenSSL may surface a given abrupt close differently; that uncertainty is correctly preserved in the trace.

---

## 3. Is `suppress_ragged_eofs=False` the narrow proposed change?

**Yes**, with one caveat.

- The unapplied diff `E5DA81D5…` is exactly one argument added at the existing covering-only `wrap_socket` call: `suppress_ragged_eofs=False`, beside the already-present `do_handshake_on_connect=False`.
- Prospective hash `76017776…` matches an in-memory UTF-8 LF replace of that single call site; **no candidate file was written**; diff was **not** applied to the tree.
- Unchanged by the proposal (static confirmation against original JoinedTLS / CoveringHTTP): CA file + hostname verification + `CERT_REQUIRED`; numeric peer / nonblocking connect+handshake; shared deadline via `remaining`/`check`; conservative `sent=True` before `send`; local `sock.close()` only (explicit “no TLS unwrap or second network exchange”); independently owned response/transport retirement and UNKNOWN rules in CoveringHTTP `finally`.

**Caveat:** Narrowness is about the *option forwarding site*. Enabling the option changes the **exception vs empty-bytes** outcome when the runtime surfaces `SSL_ERROR_EOF`. That is the intended mechanism, not scope creep — but it is still **unproved at native teardown**. Fake SSL objects can check forwarding + raise-vs-empty; they cannot prove which concrete peer teardowns produce `SSL_ERROR_EOF` vs other errors vs clean empty EOF.

---

## 4. Distinctions required (proposal language checked)

| Case | Proposal requirement | Review |
| --- | --- | --- |
| Orderly close-delimited + `close_notify` | Retain accepted positive; needs actual native TLS demonstration | Correct; do not treat source option as that proof |
| Same JSON prefix + abrupt TLS truncation | Must not become known object/token success or known `invalid_grant`; preserve UNKNOWN after possible OAuth send | Source path: unsuppressed `SSL_ERROR_EOF` → `SSLError` → CoveringHTTP oauth+`sent` → `CoveringRootOutcomeUnknown`. Still needs native proof that abrupt cases hit that path |
| Declared-length short body, valid JSON prefix | HTTP completeness gate rejects before decode/known outcome; independent of TLS orderliness | Correct; **HTTP gates remain required** (reconciled framing design). This TLS option alone does not fix F02/F03/F05-class misses |
| Complete fixed-length / correctly terminated chunked | Preserve positives; self-delimiting boundary ≠ later connection EOF | Correct; proposal explicitly forbids inventing an extra EOF read or TLS shutdown round trip after a complete message boundary — matches JoinedTLS local-close policy |
| Response/transport retirement failure | Existing primary/provenance / UNKNOWN rules | Untouched by the one-line option |

**Source mechanism ≠ observed native teardown behavior:** accepted and restated. Host byte-fakes / empty `recv` stubs are not orderly-vs-abrupt TLS proof.

---

## 5. Concrete blockers vs optional / non-blockers

### Concrete blockers (to treating this as shipped or as sole private-beta fix)

None against **accepting the recommendation as the narrow TLS-option design**.

Hold conditions that are **not** proposal defects but **block implementation/closure**:

1. **No Trish source-authoring approval** — `implementation_authorized=false`; Dex must explicitly transition before any candidate write.
2. **HTTP length/chunk completion gates still required** for short-CL / chunk-terminator contract misses; TLS option does not substitute (proposal already says keep them in one coherent acknowledgment increment).
3. **Native/synthetic TLS proof still required** for orderly `close_notify` vs abrupt truncation vs clean empty EOF under the exact runner/OpenSSL and final assembled source — separately authorized; no live provider/credentials.

### Compatibility consequences (not blockers to the design text)

- With `suppress_ragged_eofs=False`, an `SSL_ERROR_EOF` raises through `JoinedTLS.receive` into CoveringHTTP. OAuth-after-send already remaps to UNKNOWN; non-oauth re-raises. Fake observation should confirm that remapping still holds when the fake SSL raises `SSLError(SSL_ERROR_EOF)`.
- Orderly close-delimited positives must continue to complete on **clean empty read** after a complete object without demanding unwrap/shutdown. Do not conflate clean EOF with ragged `SSL_ERROR_EOF`.
- Do not expand protocol hardening (ALPN, session tickets, unwrap choreography, retry, fallback, unsafe admission). Proposal stays inside that lane.

### Optional / minimal observations (verification inventory, not new features)

| Layer | Observation | Proves |
| --- | --- | --- |
| Fake-only | Option present on wrap; `suppress_ragged_eofs is False` on fake SSLSocket; `SSL_ERROR_EOF` propagates (not turned into `b''`) | Forwarding + exception path |
| Fake-only | CoveringHTTP oauth+sent → UNKNOWN when receive raises that error; retirement provenance still independent | Caller classification / retirement unchanged |
| Fake-only | Complete fixed-length / chunked fixtures still succeed without a post-body EOF/shutdown step | Self-delimiting boundary preserved |
| Separately authorized native/synthetic | Orderly `close_notify` close-delimited retains positive; abrupt truncation does not become known success/`invalid_grant` | Real teardown distinction |
| Out of scope here | Live provider, real credentials, protocol hardening expansions | — |

---

## 6. Disposition and qualifications

**QUALIFIED ACCEPT** of the narrow TLS EOF proposal as Dex’s mechanism recommendation.

Qualifications (must travel with any tip / handoff):

1. Accepts **source-supported mechanism + one-line option** only; does **not** accept runtime/native teardown as proved.
2. Accepts that the change is **necessary but not sufficient** for acknowledgment integrity — HTTP completion/framing gates remain co-required.
3. Accepts prospective pin `76017776…` via **in-memory** reconstruct only; **no candidate authored**, **diff not applied**.
4. Does **not** authorize implementation, checker/fixture edits, imports, compilation, tests, sockets, PKI, Docker, providers, endpoint bind, launch, or Slack tip from this seat.
5. Does **not** reopen route-fake launch inference or expand beyond the covering-only `wrap_socket` option.

**REVISE** not required: trace line cites, diff text, pins, and “source ≠ native” / “no extra EOF round trip” language are consistent with the static sources.

---

## 7. Confirmation

- Ordinary reads / Get-FileHash / UTF-8 writes only.
- No application, checker, or fixture mutation.
- No imports, compilation, helper invocation, tests, sockets, PKI, Docker, providers, or execution.
- Diff not applied; candidate not written; endpoint unbound.
- No Slack tip from this seat.
