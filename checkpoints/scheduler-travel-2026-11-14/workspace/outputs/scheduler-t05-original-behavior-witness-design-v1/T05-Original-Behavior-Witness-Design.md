# T05 original-behavior witness / design preparation (documents only)

**Author:** Justin (for Jim)
**Date:** 2026-11-11
**Assignment:** Dex p1794432230 — DOCUMENTS-ONLY T05 original-behavior witness/design prep
**Flags:** documents_only=true; pplied=false; xecuted=false; launch_authorized=false
**Verdict:** **WITNESS-FIRST / NO APPLY** — freeze and observe original bounded witnesses before any completeness correction. This packet prepares the next bounded source/fixture proposal; it does **not** shrink T01–T08, invent a PASS, or authorize implementation.

## 1. Scope and holds

- Use accepted T07 source snapshot under scheduler-t07-fake-v2/packet/payload (workspace pins E942 / 2E6A / 84F5).
- Preserve the full 76-ID transport audit (59+17). T05's 13 planning IDs remain completion_unproven; chunk/trailer/close-delimited expansions remain required even where they lack final executable IDs.
- No application/checker/fixture source edits, imports/compile/tests, serialization probes, PKI, sockets, Docker, dependencies, installs, builds, or execution.
- T07 fake-v2 host QUALIFIED ACCEPT retained for bounded fake-only scope; Trish one-shot card is Dex-owned; Jim does not launch.
- Endpoint unbound. All holds stay.

## 2. Actual parser / source / caller evidence (accepted snapshot)

### 2.1 CoveringHTTP body loop (primary framing surface)

Pinned covering_http_transport.py E942…:

- Builds http.client.HTTPResponse over _SocketView → _Reader.transport.receive(min(...,8192,left+1)).
- After 
esponse.begin(), collects with **bounded** 
esponse.read(8192) until empty part, then json.loads(body) and requires a JSON **object**.
- Refuses non-identity Content-Encoding.
- **Does not** compare collected bytes to declared Content-Length, inspect remaining 
esponse.length, or independently validate chunk/trailer/final-CRLF completeness before treating JSON as a successful remote acknowledgment.
- OAuth (purpose=="oauth"): status ≥400 with exact status==400 and decoded.error=="invalid_grant" → CoveringReauthorizationRequired; any other ≥400 after decode → CoveringRootOutcomeUnknown. After 	ransport.sent, other failures remap to UNKNOWN (no retry/replay).
- Finally: independent 
esponse.close() then 	ransport.close() with explicit dual-cleanup provenance (T07 contract). Framing rejection does not itself prove retirement.

### 2.2 JoinedTLS / TLS EOF seam

Pinned covering_joined_https.py 2E6A…:

- SSLContext.wrap_socket(...) **without** passing suppress_ragged_eofs (host ssl.py default **True**).
- 
eceive returns sock.recv(maximum) bytes; empty receive is ordinary completion to the HTTP reader.
- Local sock.close() only — no TLS unwrap / close_notify exchange. Successful local close ≠ remote response completeness.

Host ssl.py (design pin only; **not** native provenance): suppress_ragged_eofs=True can convert SSL_ERROR_EOF to empty bytes before HTTP framing sees an error. Orderly close_notify vs abrupt EOF are therefore **not** distinguishable on this path without separate native/TLS proof.

### 2.3 Cumulative limits / deadlines / retirement (must survive any fix)

| Contract | Source evidence | Constraint on T05 fix |
| --- | --- | --- |
| Cumulative response-byte ceiling | pproved_provider_limits() → 16 * 1024 * 1024; _Reader/ProviderCounter.body counts **wire** bytes | Frame bytes count toward the ceiling. Do **not** move counting to decoded JSON body or raise the ceiling to make a case pass. |
| Page/item admissions | ProviderCounter.page / atch / dmit | Retain across targets; no per-exchange reset. |
| Request deadlines | CoveringRequestBudget: work 210s / request 240s / cleanup 30s; JoinedTLS/CoveringHTTP call counter.remaining / check | Do **not** replace with a fresh timeout per exchange. |
| Retirement | CoveringHTTP finally + JoinedTLS R08 + T07 provenance | Preserve dual close attempts and UNKNOWN-on-cleanup; T05 completeness is separate from T07 retirement proof. |
| Bounded reads | 
ead(8192) loop | Do **not** replace bounded reads with unbounded 
ead(). |

### 2.4 How importer / OAuth / domain classification will be observed

| Role | Transport entry | Classification observation | Notes |
| --- | --- | --- | --- |
| OAuth / token | CoveringHTTP.request(..., purpose="oauth") | Complete invalid_grant → CoveringReauthorizationRequired → domain 	oken() → TokenRejected(PREFLIGHT_ACCOUNT_DISCONNECTED) after native terminal ROLLBACK; incomplete/other after send → CoveringRootOutcomeUnknown (stop / no replay) | Prefix-valid JSON must **not** become typed invalid_grant or token success. |
| Event / identity pages | CoveringHTTP.request(..., purpose=event|identity) | Success returns httpx.Response with exact status/body; failures raise refused/UNKNOWN into importer/domain | Pair each negative with same valid bounded object and same caller purpose. |
| Importer | covering_refresh_import / import_covering_subscription_cache under covering_provider_transport | Observes transport exceptions; UNKNOWN must survive and block unsafe continuation | Event known-failure still needs acknowledged DB rollback/parent retirement (T07); provider retirement remains separate evidence. |
| Production Google helper | google_calendar.refresh_access_token still uses calendar_client (httpx) | **Not** the CoveringHTTP framing path | Do not claim T05 CoveringHTTP witnesses close legacy httpx token helpers. Covering domain path uses _refresh_provider_access_token under covering transport context. |

## 3. Standards vs current source (design hypotheses, not executed accepts)

From Dex framing reconciliation (RFC 9112 / 9110):

1. Shorter-than-Content-Length body is incomplete; valid JSON does not establish the boundary.
2. Chunked responses need data separators, terminal zero chunk, trailer section, final CRLF.
3. Close-delimited HTTP remains supported; under TLS, completion without length/chunk requires a valid closure alert. Complete length/chunk framing can complete despite incomplete TLS closure.
4. TE takes precedence over CL, but coexistence ought to be an error; conflicting lengths are unrecoverable.
5. Identical repeated decimal Content-Length values: recipient **may** reject **or** coalesce — blanket rejection is permitted, not uniquely mandated.

Host http.client branches (design pin; not native proof): bounded 
ead(amt) can EOF with nonzero remaining length without IncompleteRead; chunk path does not verify data-separator CRLF **values**; trailer collection can end on EOF without final blank line and still appear complete to chunk state. These motivate **distinct original witnesses**, not a claimed native defect.

## 4. Witness map — planning IDs × concrete stimuli × required evidence

Positive compatibility controls that **must be preserved** (do not silently reject):

- Complete fixed-length object (F01 / T05-VALID-COMPLETE-CONTENT-LENGTH)
- Complete chunked object including valid extensions/trailers where supported (F06 / C-BASE / T05-VALID-COMPLETE-CHUNKED)
- Orderly TLS close-delimited complete object **if** policy retains close-delimited support (F11) — decision below

### 4.1 Fixed-length and JSON-prefix family

| Witness ID | Stimulus (CRLF = 0D 0A) | Maps to audit ID(s) | Actual source/parser evidence to drive | Required oracle (original run) |
| --- | --- | --- | --- | --- |
| F01 | 200 + Content-Length: 2 + body {} | T05-VALID-COMPLETE-CONTENT-LENGTH | CoveringHTTP read loop + decode + purpose classification | PASS object; exact bytes; both closes; no extra exchange |
| F02 | Same headers with Content-Length: 3, body {} then EOF | T05-SHORT-LENGTH-VALID-JSON | Bounded read EOF with remaining length; JSON still parses | **Not** successful object exposure; record actual raise/class; UNKNOWN if oauth send possible |
| F03 | 400 + CL = len({"error":"invalid_grant"})+1, body exact object then EOF | T05-SHORT-LENGTH-VALID-JSON + T06-TRUNCATED-ACK | OAuth decode path would see valid invalid_grant **if** accepted | Must **not** become CoveringReauthorizationRequired; observe send + UNKNOWN/no-replay |
| F04 | Exact matching CL + complete invalid_grant object | T06-INVALID-GRANT-* (paired) | OAuth complete path | Typed reauth only after complete framing + retirement/terminal contract |
| F05 | Token-success-shaped object with CL = actual+1 then EOF | T05-SHORT-LENGTH-VALID-JSON + T06-SUCCESS-* truncated twin | Same loop | No acknowledged token success; no persist; UNKNOWN if sent |
| F05b | Exact matching CL + complete token-success-shaped object | positive twin | Same | Success only with complete framing; still subject to terminal/retirement |
| F12a | Complete framing + invalid JSON / array / scalar / null | T05-MALFORMED-JSON, T05-NONOBJECT | json.loads / isinstance(dict) refuse | No partial exposure; purpose-specific classification |
| F12b | Complete framing + non-identity Content-Encoding | T05-ENCODING | header check before body loop | CoveringTransportRefused |

### 4.2 Chunk / trailer family (cannot collapse into one truncated-CL case)

| Witness ID | Chunk spelling | Maps to | Required observation |
| --- | --- | --- | --- |
| C-BASE / F06 | 2 CRLF {} CRLF 0 CRLF CRLF | T05-VALID-COMPLETE-CHUNKED | Complete positive; retirement independent |
| C-DATA-SHORT / F07 | size 3, only {} then EOF | T05-CHUNK-EOF | Incomplete chunk-data; no object success |
| C-SEP-SHORT | 2 CRLF {} then EOF or one sep byte | T05-CHUNK-EOF expansion | Distinct short-separator branches |
| C-SEP-WRONG | 2 CRLF {} XX 0 CRLF CRLF | F09 / malformed | Two wrong separator bytes ≠ validated CRLF; record accept/reject |
| C-ZERO-ABSENT | 2 CRLF {} CRLF then EOF | F08 / T05-CHUNK-EOF | Missing terminal chunk |
| C-TRAILER-EOF | 2 CRLF {} CRLF 0 CRLF then EOF | F08 expansion | Missing final blank line; **parser flag ≠ oracle** |
| C-ZERO-NO-CRLF | 2 CRLF {} CRLF 0 then EOF | expansion | Terminal size without its CRLF |
| C-TRAILER-LINE-EOF | trailer field present, final terminator missing | expansion | Trailer line ≠ trailer completion |
| C-TRAILER-MALFORMED | invalid trailer field + final blank | F09 | Framing completeness vs trailer syntax policy |
| C-EXT-VALID | valid chunk extension on size line + complete terminators | positive compatibility | **Preserve** — do not silently reject extensions |

### 4.3 Header-length policy family

| Witness ID | Stimulus | Audit ID | Disposition rule for proposal |
| --- | --- | --- | --- |
| H-DUP-IDENTICAL | two identical decimal Content-Length | T05-DUPLICATE-CONTENT-LENGTH | **Decision D1** — reject vs coalesce (RFC 9110 allows either) |
| H-DUP-CONFLICT | conflicting lengths | T05-CONFLICTING-CONTENT-LENGTH | Must be unrecoverable framing error; observe current parser/app |
| H-TE-CL | Transfer-Encoding: chunked + Content-Length | T05-TE-CHUNKED-PLUS-CL | TE precedence + coexistence ought to error — **Decision D2** on app strictness |
| H-TE-NONEXACT | non-exact TE coding + CL | T05-TE-NONEXACT-PLUS-CL | Separate exact input; do not merge with chunked+CL |
| H-MALFORMED | invalid/negative CL or malformed header block | T05-MALFORMED-HEADER | Separate IDs; no generic "malformed" umbrella at freeze |

### 4.4 Close-delimited TLS family

| Witness ID | Stimulus | Required proof layer |
| --- | --- | --- |
| CD-ORDERLY / F11 | no CL/TE; complete {}; orderly TLS close_notify | Positive only if policy retains close-delimited; needs **native TLS provenance**, not fake empty recv |
| CD-ABRUPT | no CL/TE; {}; abrupt peer EOF / ragged EOF | Contrast with orderly; host suppress_ragged may erase error — record actual native behavior |
| CD-DEADLINE | stall / deadline during close-delimited read | Budget/deadline stop; not a silent success |

Byte fakes can characterize HTTP framing application behavior; they **cannot** close T03/T04 real JoinedTLS CA/hostname/handshake/disconnect obligations or prove close_notify.

## 5. Prefix-versus-complete (token-success / invalid_grant)

Hard rule for every oauth-purpose witness:

1. A syntactically valid JSON **prefix** that equals a complete invalid_grant or token-success object is **not** a complete remote acknowledgment when declared framing is incomplete (F02/F03/F05 and chunk twins).
2. Complete invalid_grant (F04) is the only path to CoveringReauthorizationRequired / domain disconnect reject.
3. Complete token-success-shaped framing is required before any TokenReady / persistence; truncated success → UNKNOWN if send occurred.
4. Do not substitute DB rollback acknowledgment for provider framing completeness.
5. Event/identity purposes get the same framing completeness gate before object exposure, with their own caller classification.

## 6. Narrowest correction options (unapplied; witness-first)

**Do not apply now.** Original witnesses first. Options below are the narrowest candidates that respect Dex's hard constraints (no unbounded reads; no silent reject of close-delimited / chunk-extension / trailer positives; no invented PASS).

### Option A — Fixed-length remaining-length gate (narrowest for F02/F03/F05)

After the body 
ead(8192) loop and **before** json.loads, if the response carried a definite length and remaining length is still >0, refuse success and raise purpose-correct uncertainty/refusal **without** decoding.

Sketch (illustrative, not applied):

`python
# documents-only sketch — NOT applied
remaining = getattr(response, "length", None)
if remaining is not None and remaining > 0:
    if purpose == "oauth" and transport.sent:
        remapped = CoveringRootOutcomeUnknown()
        invocation_primary = remapped
        raise remapped
    raise CoveringTransportRefused("incomplete content-length body")
`

- Pros: targets the known bounded-read EOF hole; keeps 
ead(8192); counts already-charged wire bytes; no ceiling change.
- Cons: does **not** close chunk trailer-EOF / wrong-separator holes; does not settle close-delimited policy; must still independently observe caller/retirement.

### Option B — Explicit close-delimited policy branch (requires Decision D3)

If no CL and not chunked: either (B1) retain support and require later native orderly close_notify proof, or (B2) refuse close-delimited at application layer. **B2 is a compatibility restriction** — bring to Trish before implementation. Do not silently flip suppress_ragged_eofs=False inside a fixture task (Decision D4).

### Option C — Chunk completeness (post-witness)

Only after C-* original witnesses record actual accept/reject: propose the smallest additional checks that catch trailer-EOF / wrong-separator **without** rejecting C-BASE / C-EXT-VALID / valid trailers. Likely **not** solvable by 
esponse.length alone. May need rejected incomplete states surfaced as UNKNOWN/refuse before JSON success. Exact diff deferred until witness receipts exist.

### Explicitly rejected "fixes"

- Unbounded 
esponse.read() to force IncompleteRead.
- Reject-all close-delimited or reject-all chunk extensions/trailers to avoid proof work.
- Treating 
esponse.isclosed() / local 	ransport.close() success / JSON decode alone as completion.
- Raising or relocating the 16 MiB cumulative ceiling.
- Inventing PASS for truncated-but-JSON-valid bodies.

## 7. Real decisions needed (Trish / Dex gate)

| ID | Decision | Why it blocks implementation |
| --- | --- | --- |
| D1 | Identical duplicate Content-Length: **reject** vs **coalesce** | RFC permits either; chooses H-DUP-IDENTICAL expected outcome |
| D2 | TE: chunked + Content-Length coexistence: application **error** vs parser-follow-TE-only | Standards prefer error; must match frozen oracle |
| D3 | Retain close-delimited positives (with native close_notify proof) vs restrict to CL/chunk only | Compatibility impact; Synthetic-Provider topology still separate |
| D4 | Keep suppress_ragged_eofs default True vs explicit False | Changes TLS EOF visibility; needs compatibility brief + native provenance |
| D5 | Native parser/SSL inventory pin for the real runner image | Host http.client/ssl pins are **not** native proof; required before claiming native acceptance |

No Decision here adopts a restriction. Implementation/verification prep gates return through Dex/Trish after this brief.

## 8. Fixture / topology boundary (from Synthetic-Provider-Topology-Review)

- Prefer reusable I01/I02 disposable patterns for later real TLS peers; new separately approved fixture, not reuse of deleted containers.
- High-port numeric HTTPSPeer is describable; do not invent hidden connect-port translation for www.googleapis.com:443 URL builders.
- Seams: (1) CoveringHTTP/JoinedTLS synthetic hostname/high-port, (2) importer/domain with disclosed synthetic callback, (3) full 443 composition — each discloses coverage limits.
- This documents-only packet authorizes **none** of those topologies.

## 9. Recommended next bounded prep (after Dex reconcile)

1. Keep this brief frozen; no source edits.
2. Dex/Trish resolve D1–D5 as needed for oracle freeze.
3. Author a later **fixture-prep** packet: exact byte transcripts + hashes for F01–F12 / C-* / H-* / CD-* paired by purpose (oauth/event/identity), pinned host **and** planned native parser pins, expected original outcomes (including UNKNOWN), retirement observations — still no execution until card.
4. Only after original witness receipts: choose Option A/B/C (or narrower), return fresh-copy proposed diff with prospective SHAs under existing source-change hold.

## 10. Explicit non-claims

- No PASS claimed for any T05/T06 ID.
- No native parser/SSL/OpenSSL behavior proved.
- No close_notify proved.
- No T01–T08 family closed; 76-ID audit remains incomplete.
- No T07 one-shot launched; fake-v2 packet untouched by this work.
- No application/checker/fixture bytes modified.

## Confirmation

Documents/proposed-options only. Predecessors preserved. Endpoint unbound.
