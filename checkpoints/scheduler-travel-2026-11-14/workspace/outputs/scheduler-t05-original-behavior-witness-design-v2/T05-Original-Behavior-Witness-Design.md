# T05 original-behavior witness / design v2 (documents only)

Author: Justin (for Jim)
Date: 2026-11-11
Assignment: Dex REVISE on tip thread Ev0CH04PEKED / Reply-Ev0CH04PEKED.txt
Supersedes: v1 tip 8C32BFEC... (immutable; formatting artifacts preserved there)
Flags: documents_only=true; applied=false; executed=false; launch_authorized=false
Verdict: WITNESS-FIRST / NO APPLY -- original predictions separate from corrected acceptance; no source edits.

## 1. Scope and holds

- Fresh documents-only successor. v1 packet untouched.
- Full 76-ID transport audit preserved (59+17). T05 x13 remain completion_unproven; expansions are variants, not a replacement inventory.
- No application/checker/fixture source edits, imports/compile/tests, PKI, sockets, Docker, live probes, or execution.
- T07 fake-v2 card pending unchanged. Endpoint unbound. All holds stay.
- Provenance layers kept separate: host Py3.11 analysis; published upstream CPython 3.12.16 reference; eventual captured native runner bytes (UNESTABLISHED).

## 2. Actual source evidence (accepted T07 snapshot)

### 2.1 CoveringHTTP body loop

Pinned covering_http_transport.py E942...:

- HTTPResponse over SocketView/Reader with transport.receive(min(..., 8192, left+1)).
- Collects via bounded response.read(8192) until empty, then json.loads(body); requires a JSON object.
- Refuses non-identity Content-Encoding.
- Does not compare collected bytes to declared Content-Length, inspect remaining response.length, inventory raw duplicate headers before dict conversion, or validate chunk/trailer/final-CRLF completeness before success.
- OAuth purpose: status 400 with decoded.error == invalid_grant raises CoveringReauthorizationRequired; other >=400 after decode raises CoveringRootOutcomeUnknown; after transport.sent, other failures remap to UNKNOWN (no retry).
- Finally: independent response.close then transport.close with explicit dual-cleanup provenance (T07).

### 2.2 JoinedTLS / TLS EOF seam

Pinned covering_joined_https.py 2E6A...:

- wrap_socket without suppress_ragged_eofs argument (published 3.12.16 / host default True).
- receive returns sock.recv bytes; empty receive looks like ordinary EOF to HTTP.
- Local sock.close only -- not close_notify proof.

### 2.3 Google / calendar_client routing (corrected)

Pinned covering_provider_context.py 875F...:

- calendar_client(timeout=...) reads ContextVar covering_provider_transport.
- If transport is set (inside covering_provider_transport(...)): returns _CoveringClient, which delegates get/post to transport.request(...) i.e. CoveringHTTP with resolved purpose.
- If transport is None: returns ordinary httpx.Client(timeout=...).

Therefore google_calendar.refresh_access_token (and other calendar_client callers) use CoveringHTTP framing when invoked under covering_provider_context.covering_provider_transport, which is how covering_domain_adapters.token/apply call _refresh_provider_access_token / import. The same helpers outside that context use ordinary httpx -- a different path, not "categorically outside covering."

Separate proof layer retained: token-adapter native terminal (RootOutcome COMMIT/ROLLBACK acknowledgment) is not replaced by transport framing proof.

### 2.4 Cumulative limits / deadlines / retirement

| Contract | Evidence | Constraint |
| --- | --- | --- |
| Wire byte ceiling | approved_provider_limits response_bytes = 16 MiB; ProviderCounter.body | Frame bytes count; do not move counting to JSON body |
| Admissions | page / batch / admit | Retain across targets |
| Deadlines | CoveringRequestBudget work 210s / request 240s / cleanup 30s | No fresh timeout per exchange |
| Retirement | CoveringHTTP finally + JoinedTLS R08 | Preserve dual close + UNKNOWN-on-cleanup |
| Bounded reads | read(8192) loop | Do not switch to unbounded read() |
| Stall stops | first actual guard | Record parser interim/trailer cap, 16 MiB, deadline, disconnect, or retirement -- do not assume unlimited 1xx/trailer reaches the timer |

## 3. Column rules: ORIGINAL vs CORRECTED

Every witness row uses two columns:

1. Predicted ORIGINAL observation (source hypothesis): what current code/parser may do. If the hypothesis is a contract miss (e.g. valid-prefix JSON accepted), the original run must be allowed to exhibit that miss. The original oracle must NOT require the intended fix to already be present, and must NOT accept arbitrary unexpected failures as PASS_WITNESS.
2. Desired CORRECTED acceptance (future): post-fix oracle, frozen separately, not used to score original runs.

Witness outcome classes for original characterization (to freeze later per input):

- OBSERVED_SUCCESS -- application exposed object / typed invalid_grant / token path success
- OBSERVED_REFUSE -- CoveringTransportRefused or equivalent before typed success
- OBSERVED_UNKNOWN -- CoveringRootOutcomeUnknown (incl. oauth-after-send remap)
- OBSERVED_PARSER_ERROR -- parser exception surfaced to application
- OBSERVED_STOP_GUARD -- first stop was ceiling/deadline/cap/disconnect (record which)
- CONTRACT_MISS -- OBSERVED_SUCCESS where framing was incomplete (recorded honestly)
- UNEXPECTED -- anything outside the frozen prediction set for that input (stops; no repair)

## 4. Witness map (CRLF = bytes 0D 0A)

Positive compatibility baselines to preserve (do not silently reject):

- Complete fixed-length object (F01)
- Complete chunked object including valid chunk extensions and valid trailers (C-BASE / C-EXT-VALID)
- Close-delimited complete object with orderly TLS close_notify (CD-ORDERLY) -- retained baseline support

### 4.1 Fixed-length and prefix-vs-complete

| ID | Stimulus | Predicted ORIGINAL | Desired CORRECTED | Audit / notes |
| --- | --- | --- | --- | --- |
| F01 | 200, CL=2, body {} | OBSERVED_SUCCESS object; both closes | unchanged success | T05-VALID-COMPLETE-CONTENT-LENGTH |
| F02 | 200, CL=3, body {} then EOF | Likely CONTRACT_MISS: bounded read EOF may yield valid JSON object success without IncompleteRead | Refuse incomplete CL before decode; no object exposure | T05-SHORT-LENGTH-VALID-JSON |
| F03 | 400, CL=len(invalid_grant JSON)+1, body exact object then EOF, purpose=oauth | Likely CONTRACT_MISS: may raise CoveringReauthorizationRequired on prefix-valid invalid_grant | UNKNOWN (if sent) or refuse; never typed reauth on incomplete framing | pairs T06-TRUNCATED-ACK |
| F04 | 400, exact CL, complete invalid_grant JSON, oauth | OBSERVED typed CoveringReauthorizationRequired after complete framing | unchanged typed reauth + terminal/retirement layer | complete control |
| F05 | 200 token-success-shaped, CL=actual+1, EOF, oauth | Likely CONTRACT_MISS: may expose success-shaped object | No acknowledged token success; UNKNOWN if sent | truncated success twin |
| F05b | exact CL, complete token-success-shaped, oauth | OBSERVED_SUCCESS through CoveringHTTP/_CoveringClient | unchanged complete success; terminal layer separate | positive twin |
| F12a | complete framing + non-object/invalid JSON | OBSERVED_REFUSE (loads/dict check) | unchanged refuse | T05-MALFORMED-JSON / NONOBJECT |
| F12b | non-identity Content-Encoding | OBSERVED_REFUSE before body loop | unchanged | T05-ENCODING |

Hard rule: syntactically valid JSON prefix is never complete acknowledgment when framing is incomplete. Original misses are recorded as CONTRACT_MISS, not forced REFUSE in the original oracle.

### 4.2 Chunk / trailer family

| ID | Spelling | Predicted ORIGINAL | Desired CORRECTED |
| --- | --- | --- | --- |
| C-BASE / F06 | 2 CRLF {} CRLF 0 CRLF CRLF | OBSERVED_SUCCESS | unchanged |
| C-EXT-VALID | valid size-line extension + complete terminators | OBSERVED_SUCCESS (preserve) | unchanged preserve |
| C-DATA-SHORT / F07 | size 3, only {} then EOF | incomplete chunk-data; record actual | no object success |
| C-SEP-SHORT | 2 CRLF {} then EOF or one sep byte | record actual short-sep branch | no object success |
| C-SEP-WRONG | 2 CRLF {} XX 0 CRLF CRLF | may accept (sep bytes unchecked upstream) = possible CONTRACT_MISS | refuse wrong separator; do not treat two-byte count as CRLF validation |
| C-ZERO-ABSENT | 2 CRLF {} CRLF then EOF | record actual | no object success |
| C-TRAILER-EOF | 2 CRLF {} CRLF 0 CRLF then EOF | may appear complete (trailer EOF tolerance) = possible CONTRACT_MISS | refuse missing final blank line; parser flag alone insufficient |
| C-ZERO-NO-CRLF | ... 0 then EOF | record actual | no object success |
| C-TRAILER-LINE-EOF | trailer line without final terminator | record actual | no object success |
| C-TRAILER-MALFORMED | invalid trailer + final blank | record framing vs trailer-syntax policy separately | explicit disposition after witness |

Maps under T05-VALID-COMPLETE-CHUNKED / T05-CHUNK-EOF and expansions. Do not collapse into one truncated-CL case.

### 4.3 Header representation family (from Header-Representation-Witness-Review)

Upstream 3.12.16 begin uses single-value header get + int(length); Message.get returns first field; get_all exposes all. Remaining-length gates cannot see conflicts already collapsed to unspecified length. Preserve raw occurrences before dict(response.getheaders()).

| ID | Fields | Predicted ORIGINAL (hypothesis) | Desired CORRECTED direction |
| --- | --- | --- | --- |
| H-DUP-IDENTICAL-FIELDS | CL:2 then CL:2 | first-value wins; may behave as CL=2 success | see D1 recommendation |
| H-DUP-IDENTICAL-LIST | one CL: 2,2 | int() may fail -> unspecified length / close-delimited path | explicit refuse or defined coalesce; not accidental |
| H-CONFLICT-FIELDS-2-3 | CL:2 then CL:3 | first wins (CL=2) possible | unrecoverable framing error |
| H-CONFLICT-FIELDS-3-2 | CL:3 then CL:2 | first wins (CL=3); interacts with short-body EOF | unrecoverable framing error |
| H-CONFLICT-LIST-2-3 / 3-2 | one CL: 2,3 or 3,2 | characterize separately from repeated fields | unrecoverable framing error |
| H-DECIMAL-02 | CL:02 (and dup 2 vs 02) | decimal value vs raw-string equality | preserve distinction in proposal |
| H-INVALID | +2 / negative / nondecimal / empty | may become unspecified length | refuse; conversion success != valid HTTP |
| H-TE-REPEAT / H-TE-LIST | repeated TE fields vs comma coding list | first-value vs list behavior | exact variants; no collapse |
| H-TE-CL | TE chunked + CL present | TE ignored CL path varies | see D2 recommendation |
| H-TE-NONEXACT+CL | nonexact TE + CL | separate from chunked+CL | separate ID |

Planning IDs T05-DUPLICATE-CONTENT-LENGTH / CONFLICTING / TE-CHUNKED-PLUS-CL / TE-NONEXACT-PLUS-CL / MALFORMED-HEADER remain; rows above are representation variants.

### 4.4 Close-delimited TLS family (baseline retained)

| ID | Stimulus | Predicted ORIGINAL | Desired CORRECTED |
| --- | --- | --- | --- |
| CD-ORDERLY | no CL/TE; {}; orderly close_notify | may succeed via empty recv; host/upstream ragged-EOF suppression hides error path | retain as supported positive once native close_notify proven |
| CD-ABRUPT | no CL/TE; {}; abrupt EOF | may look identical to orderly under suppress_ragged_eofs=True | distinguish only with native TLS provenance; do not fake empty recv as proof |
| CD-DEADLINE | stall during close-delimited read | first stop guard recorded | unchanged stop semantics |

Reject-all close-delimited is NOT an adopted implementation shortcut. Byte fakes do not close T03/T04 real JoinedTLS obligations.

## 5. Recommendations and gates (separated)

### 5.1 Concrete recommendations (for later bounded proposal; not applied now)

D1 identical Content-Length:

- Recommendation: refuse when raw header inventory (get_all or equivalent before dict collapse) shows more than one Content-Length field, even if decimal values match.
- Compatibility impact: peers emitting duplicate identical CL fields would be refused. Google/Microsoft JSON HTTPS responses in this covering path are not known to require duplicate CL. Safer than silently adopting first-field-wins.
- Alternative (if evidence later shows required identical duplicates): coalesce only after verifying all raw values are decimal-equal; still preserve occurrence count in evidence. Requires Trish only if that compatibility case is demonstrated.

D2 TE + Content-Length:

- Recommendation: refuse coexistence of Transfer-Encoding: chunked (or any TE) with Content-Length before body collection (RFC 9112 ought-error).
- Compatibility impact: refuses non-conforming peers; preserves pure chunked positives (C-BASE / C-EXT-VALID) and pure CL positives (F01).
- TE-NONEXACT+CL stays a separate exact input.

### 5.2 Baseline (not a product fork)

D3 close-delimited: retain existing valid close-delimited support as design baseline. CD-ORDERLY remains a required positive compatibility control under later native TLS proof. Do not promote reject-all.

### 5.3 Technical / evidence gates (not Trish product choices)

| Gate | Nature | Owner path |
| --- | --- | --- |
| D4 suppress_ragged_eofs explicit False | Proposed technical source change under existing source-change hold | Dex/Jim reviewed fresh-copy scope after witnesses; compatibility brief if behavior changes |
| D5 native http.client / ssl / email.message bytes from runner c2201104... | Evidence acquisition under launch/provenance gate | Later reviewed packet; version string 3.12.16 insufficient to equate upstream tag |

Do not block useful prep on asking Trish to vote five routine investigation steps.

## 6. Narrowest correction options (unapplied; after original witnesses)

Option A -- Fixed-length remaining-length gate after read loop, before json.loads, when response.length remaining > 0. Keeps read(8192). Does not fix chunk trailer-EOF, wrong separators, or header-representation collapse.

Option B -- Close-delimited: keep support; pair with native close_notify / abrupt distinction (D4 only if witnesses show need). No reject-all.

Option C -- Chunk completeness checks after C-* original receipts; must preserve C-BASE / C-EXT-VALID / valid trailers.

Rejected: unbounded read(); inventing PASS; raising 16 MiB ceiling; treating isclosed/local close/JSON alone as completion.

## 7. Explicit non-claims

- No PASS for any T05/T06 ID.
- No native parser/SSL/message bytes proven.
- No close_notify proven.
- No T01-T08 family closed.
- No T07 launch; fake-v2 untouched by this packet.
- No application/checker/fixture bytes modified.

## Confirmation

Documents only. v1 preserved. Endpoint unbound.
