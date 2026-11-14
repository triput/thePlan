# Native T05 fixture: focused fake verification preparation v2 (HELD)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-Native-T05-Preparation-2026-11-13.md` (`62E314AB…3B84`). It's the companion to the frozen `scheduler-native-provider-t05-prep-matt-v2` (parent `C36E3078…5ACF`).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Roles and pins
- **Reused byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker **`93E21A341A8C3CBF9C8D0B56DDF8433B0453CC1C2F5F0CA46CCDE121EE406B9A`**;
  - EXPECTED **`8D9B27B6D4FAEB42927959E73883FD4661245BD3D20F98DFBCDCCDBAADA99C3C`**;
  - OUTER (see the packet manifest);
  - VERIFICATION **`E2D32E860C943A50466F761C765FB4430A042B8A6270F5C4D8091E6F9C13405E`** (28 packet pins and 10 runtime pins, all re-verified).
- **Runtime (partial scope):** `python.exe`, `python311.dll`, `http/client.py`, `json/__init__`/`decoder`/`scanner`, `email/feedparser`/`parser`, `socket.py`, `ssl.py`. Importing `http.client` loads `socket` and `ssl`, but no socket or SSL object is constructed.

## Controls (13 top-level, 60 nested, in order; v2 adds 3, see below)
1. **SUBJECT-PINS** (22 subjects).
2. **RUNTIME-PROVENANCE** (7).
3. **DIFF-REDERIVATION** (5): runner (3 hunks), peer (1), transcript (4), suite (1), runner-config (1).
4. **PRESERVED-OUTSIDE-CHANGE** (4): exact top-level partitions for runner, peer, transcript and suite.
5. **SERIALIZER-DEFAULT-REGRESSION** (4): every send step of `finite_script_catalog`, the MS NONEXPIRED and MS REFRESH inventories has equal step fields, framing `auto`, and **byte-identical source and candidate wire**. The only changed script is `T05-ORDERLY-CLOSE-DELIMITED-COMPLETE`.
6. **CLOSE-DELIMITED-SERIALIZATION** (3): the exact bytes; no CL/TE header; the source serializer would append `Content-Length: 2`.
7. **INVALID-MODE-REFUSALS** (5): an unknown mode, `close_delimited` plus CL, `auto` plus TE, and `close_delimited` plus TE are each refused with `PeerLifecycleError`. The unchanged `_send_response` serializes before any `_send_all`.
8. **CLIENT-COMPLETENESS-VS-DECODE** (4), the actual transport and policy over the host `http.client` with the exact candidate serializer bytes:
   - close-delimited complete is accepted (200, `{}`, no CL/TE; gate then json);
   - short-CL valid-JSON gives `IncompleteRead` (expected 18) at the guarded read, with json 0 and gate 0;
   - close-delimited invalid JSON gives `JSONDecodeError` from the real decoder (json 1, gate 1; not framing);
   - an injected transport error object propagates unchanged.
   - The fake `b""` EOF models a client-read orderly close. **It isn't native TLS proof.**
9. **OUTCOME-CLASSIFIER** (7): the extracted `_t05_classify_client_outcome` gives the exact labels for the exact outcomes, and a STOP for every other outcome, class or expectation.
10. **RUNNER-WIRING** (5):
    - `CoveringHTTP(counter=…, routes=…)` with no `transport_factory`, the production counter construction, and the `JoinedTLS` assertion;
    - framing validated before the peer starts;
    - `retire_owned` first in the `finally`, then `sanitized_state`, before classification;
    - both bodies call oracles before the receipt (`passed`, `workers_joined` true; `expected_unknown` false);
    - the mapper and the 4-ID set.
11. **BATCH-CONFIG** (3): runner and launch configs for exactly the two T05 IDs, gates false, own manifest pin and own root, no foreign root; the payload delta is exactly 5 rows.
12. **PRIOR-FAKE-APPLICABILITY** (3): the peer class is identical and the serializer changed; the merge units are identical; the unchanged transcript functions are identical. **Non-transferred claims are listed in the result.**
13. **ACTUAL-SOURCE-MUTANTS** (6), each detected only by its targeted prefix:
    - close-delimited appends a length;
    - Transfer-Encoding refusal removed;
    - auto path altered;
    - abrupt accepts `IncompleteRead`;
    - `transport_factory` injected;
    - retirement removed.

## Claims that do NOT transfer (current prerequisite named)
- **Peer-close fake PRESERVED** ("only `_close_connection` differs from `5568`"): the serializer changed too. Prerequisite: SERIALIZER-DEFAULT-REGRESSION.
- **MS-refresh fake v2 OAUTH-ROUTE-TABLE** (it executed the old serializer). Prerequisite: SERIALIZER-DEFAULT-REGRESSION wire equality.
- **MS-refresh fake v2 transcript-derived controls** (`ExchangeStep` gained a defaulted field). Prerequisite: step-field equality plus `transcript_functions_identical`.
- **Merge fake ROLE-SELECTION peer row `17EA148E`:** it doesn't describe this root (peer `BFB271D7`).

## Not proved
- **Native behavior:** native TLS close_notify/EOF behavior, the native client classes, native peer retirement.
- **T05 scope:** any T05 requirement beyond these finite fixture properties.

## Limits
- **Timing:** 120 s, plus at most one 5 s kill/wait, plus two 5 s reader joins: 135 s nominal, with no separate outer timeout.
- **Capture:** 64 KiB per stream; 256 KiB for the result.
- **Success** requires exit 0, no output, clean readers and the exact inventory; a failure stops and preserves.

## Future command
`Future-Command-HELD.ps1.txt` (admission `E2D32E86…`).

## v2 additions (Dex P1 `F56020E8…5CE0A`; v1 preserved at `scheduler-native-t05-fake-prep-matt-v1`)
- **The trap:** production rebuilds the returned API object as `httpx.Response(status, content=bytes(body), headers=dict(response.getheaders()), …)`, and httpx 0.28.1 supplies Content-Length for non-empty bytes content. The candidate runner `EB76303F` therefore judges framing on the **exact scripted wire** through the pure `_t05_response_outcome`, and never reads `response.headers`.
- **CLIENT-COMPLETENESS-VS-DECODE `rebuilt_content_length_trap`:**
  - an httpx-0.28.1-style recorder (`AutoLengthHttpxResponse`) reproduces `Content-Length: 2` on the rebuilt close-delimited response, yet the extracted `_t05_response_outcome` plus the classifier still **accept** it;
  - a truly Content-Length-framed wire for the same body gives `scripted_wire_framing_headers_absent=False` and **STOPs**.
  - The real negative framing, completeness and exact-body checks are kept.
- **RUNNER-WIRING `no_rebuilt_header_oracle`:** `_t05_observe` has no `response.headers` attribute access (AST), and exactly one call `_t05_response_outcome(response.status_code, response.content, expected_body, expected_wire)`.
- **ACTUAL-SOURCE-MUTANTS `wire_framing_predicate_dropped`:** the predicate is replaced with `True`, which is detected at "client:rebuilt trap negative".
- **Subjects refreshed:**
  - runner candidate `EB76303F`;
  - runner diff `AAC99686`;
  - candidate launch-config `3B98C20F`;
  - candidate payload manifest `98BE4F8E`.
- **OUTER and VERIFICATION re-pinned:** VERIFICATION is `E2D32E86…`.
- **Secondary qualification (Dex):** `peer_side_wire_bytes_sent_exact` and the abrupt script prove the peer-side stimulus only. Claims stay limited to the client's actual EOF outcome.
