# Native T05 fixture: focused fake verification preparation (HELD)

Matt, November 13, 2026. This is for assignment `Matt-thePlan-Scheduler-Native-T05-Preparation-2026-11-13.md` (`62E314AB…3B84`). It's the companion to the frozen `scheduler-native-provider-t05-prep-matt-v1` (parent `704A16D1…39B0`).

**No execution is authorized.** Nothing here has been imported, parsed, compiled or run. Both admissions have `launch_authorized=false`. No PASS is claimed.

## Roles and pins
- **Reused byte-identical:** wrapper `AE84E632`, outer `7DCA32E2`, launcher `D22C37E3`.
- **New:**
  - checker **`6318895035B8FC5C7D98215EDCCB5BDF987CE82596307EBAB5F0F553A0E179CC`**;
  - EXPECTED **`795AFC6F924EC7E6BCA8A330B9FA84632C572DBAB2CDEF61A44FB9240A7648C7`**;
  - OUTER (see the packet manifest);
  - VERIFICATION **`B6F944606D86794B6138BCB6546E0DFD2B7B2CA9AAFAC4954C6453F75FCC70E3`** (28 packet pins and 10 runtime pins, all re-verified).
- **Runtime (partial scope):** `python.exe`, `python311.dll`, `http/client.py`, `json/__init__`/`decoder`/`scanner`, `email/feedparser`/`parser`, `socket.py`, `ssl.py`. Importing `http.client` loads `socket` and `ssl`, but no socket or SSL object is constructed.

## Controls (13 top-level, 57 nested, in order)
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
`Future-Command-HELD.ps1.txt` (admission `B6F94460…`).
