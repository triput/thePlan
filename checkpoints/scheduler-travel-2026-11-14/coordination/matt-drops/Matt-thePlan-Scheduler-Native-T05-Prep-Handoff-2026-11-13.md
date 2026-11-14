# Matt → Dex: native T05 fixture preparation plus focused fake (HELD, frozen)

November 13, 2026. This responds to `Matt-thePlan-Scheduler-Native-T05-Preparation-2026-11-13.md` (`62E314AB62C80BC5EB9214976A097506F23C37B9903EBEE06D9F4B73038F3B84`), under lane `389A00DD…7E2D`. Design input: `Next-Native-T05-Design-Notes-2026-11-13.md` (`9879751E…7C5B`).

**Status:** PREPARED_NOT_EXECUTED. Both roots are frozen with no active writer, and every gate and admission flag is false. There's no EXECUTE acknowledgement, and the endpoint is unbound. Nothing was imported, parsed, compiled or run. No subagents were used. Earlier roots and their one-shot command versions are untouched.

## 1. Native root `outputs/scheduler-native-provider-t05-prep-matt-v1`
- **Copy:** the 286 manifest inputs of the frozen MS-merge NONEXPIRED root (`22AE4F82…CDC7`), verified 286/286.
- **Manifests:** nested **`9913B554D14A0E59680C3D7D0369148B9E5B43FB4EB74F8A3EF03F3BC8C94104`** (269), parent **`704A16D157E5BF3E6CD227DA3296E90323237BABF267484CEF4B37A3805C39B0`** (290), both 0 mismatches.
- **Evidence root:** absent.
- **Batch:** `["NP-T05-ORDERLY-CLOSE", "NP-T05-ABRUPT-TRUNCATION"]`, with `expected_unknown_cases` `[]` and `batch_id` `np-t05-orderly-and-abrupt`. There's no sequencing or retry. NONEXPIRED and REFRESH stay in their frozen roots.

### Source lineage table
| role | file | source (MS-merge NONEXPIRED) | candidate | delta |
|---|---|---|---|---|
| 4 | `np_runner_entry.py` | `F7CFD3E6` | **`E75F7C2426662A1AE68DF7D31998197916960E757998D21184FF388D2EAA4827`** | 3 hunks, +240/−1 |
| 5 | `np_suite.py` | `46C9443D` | **`E5C63D9CE7AA3E66784216B0E88D14434F7016E67E6D22931C58504D87209189`** | +11 (notes only) |
| 7 | `np_provider_peer.py` | `17EA148E` | **`BFB271D770D08BC161E9613564ECA799B7E28884D8211E10228F5973A4A271BF`** | +19/−0 |
| 8 | `np_provider_transcript.py` | `0AA3BC09` | **`46455CD603355E30819FBF944ADAC141DDE04D78E28C4F25783681A67A0212D8`** | 4 hunks, +16/−3 |
| data | `runner-config.json` | `9411AC38` | **`96782CB425239BC6F121949DABE16B4B53528E249BE625DD25A9811DA7D07E71`** | `case_ids` only |
| — | payload `SHA256SUMS.txt` | `14FA30AD` | **`62E29339859E81234A637E4794682912278B8A4D6DEC0794179C53A52582C54E`** | 5 rows |
| host | `launch-config.json` | — | **`653132D0B5315EE5936D1D8CDC31F0AD332A506C736AF9F66757C46367D1DF41`** | batch id, cases, implemented list, 2 roots, manifest pin, note |
| host | `docker-ops-config.json` | — | **`1985CF6452773D4D02E35AA6C8ACD70CD89114A4107C1A2D6B81757BBB3D2A69`** | 7 roots |

**Unchanged:**
- the operator `5A8A04B6`, supervisor `A1ADA231`, Docker helper `7F7EA820`, integrated runner, bootstrap and DB helpers;
- roles 6 and 10;
- all 234 API files;
- the observer and refresh units, `stop_payload`, and every existing assertion;
- all 31 case declarations and all 76 planning IDs.

**Exact diff:** `Matt-thePlan-Scheduler-Native-T05-Prep-2026-11-13.diff` (`EECE5281…81B0`), the five per-file diffs concatenated.

### What changed
- **Peer `_http_response_bytes`:** an inserted prefix (+19/−0). The historical `auto` lines are untouched, so default wire bytes are identical (fake-checked for every existing script).
  - `close_delimited` sends no Content-Length and no Transfer-Encoding.
  - **These are refused before any send:** an unknown mode, any Transfer-Encoding header (the old serializer would have appended a conflicting length), and Content-Length together with `close_delimited`.
  - Chunk framing is **not** added. It stays explicitly open, and no chunk case was invented.
- **Transcript:** `ExchangeStep.framing` (default `"auto"`). The `T05-ORDERLY-CLOSE-DELIMITED-COMPLETE` script really is close-delimited now; before, it declared `Content-Length: 2`.
- **Runner:**
  - **`_t05_observe`:**
    - uses the production contract `CoveringRequestBudget()` → `ProviderCounter(approved_provider_limits(), budget.work_remaining)` → `CoveringHTTP(counter, routes)` with the **default JoinedTLS** (asserted), on Google event routes, numeric loopback :443 and verify-full (the provider certificate's SANs include `www.googleapis.com`);
    - validates the framing before the peer starts;
    - retires and joins the peer in `finally`;
    - refuses an unjoined peer, worker error, inventory or wire-length mismatch as a STOP **before** classification, whatever the client saw.
  - **`_t05_classify_client_outcome`:** finite and fail-closed. Exact `(response, 200, body_exact, no CL/TE)` is accepted; exact `http.client.IncompleteRead` is the short-CL refusal; exact `ssl.SSLEOFError` or `builtins.ConnectionResetError` is the abrupt distinction. **Everything else is a STOP.**
  - Two bodies, the mapper branches and `IMPLEMENTED_CASE_IDS` (4).
- **Report:** the existing `case_result_receipt`. `measured` holds only class names, booleans, status and script ids; the sanitized peer inventory and retirement are included. There are no bodies, header values, credentials or messages. STOP diagnostics stay class and location only. **No schema is widened.**

### Expected native outcomes (source-derived; nothing observed natively)
- **ORDERLY (a), close-delimited `{}`:** the peer sends the body and then close_notify. Per `_ssl.c`, `SSL_ERROR_ZERO_RETURN` with received shutdown returns `b""`, so the guarded read with `length=None` reaches EOF. The gate admits, json decodes, and the client sees 200 with the exact body → `ACCEPTED_AFTER_ORDERLY_CLOSE_NOTIFY`.
- **ORDERLY (b), CL 20 with `{}`:** the client reads `{}`, then the orderly EOF arrives. The covering guarded read raises `IncompleteRead(b"", 18)` before decoding → `REFUSED_AFTER_ORDERLY_CLOSE_NOTIFY`.
- **ABRUPT, CL 20 with `{` then an SO_LINGER-0 shutdown and close without close_notify:** with `suppress_ragged_eofs=False`, the client should see `SSLEOFError`, or `ConnectionResetError` if the RST is seen first → `OBSERVED`.
- **Any other class STOPs.** I'm asserting these only from source, not from the host fake.
- **Peer unwrap `OSError`:** tolerated (the `17EA148E` behavior, kept). An attempt note is never the oracle.

### Held native command (not authorized)
- **`T05-Native-Command-HELD.ps1.txt`** (`B680CA3C…E684`): the absolute operator in this root, `-ExpectedConfigSHA256 653132D0…`, `-ExpectedDockerConfigSHA256 1985CF64…`, this root's `-DockerConfigPath`, and no `-ReceiptPath`. The operator STOPs on the false gates.
- **Current docs:** `T05-PREP-README.md` `850E5CA4…DA9D` and `T05-Prep-Freeze.json` `FBB30D98…1F9C`.
- **Bounds (unchanged):** 900 s suite, 600 s runner, 120 s peer plus 5 s join per observation (three peers in sequence), PKI 45 s, 32 / 22 Docker commands, 1 MiB per command plus a 1 MiB report; startup, outer, file, hash and OS time excluded; no separate outer timeout; CLI kill doesn't wait.

## 2. Focused fake `outputs/scheduler-native-t05-fake-prep-matt-v1`
- **Roles:**
  - reused byte-identical: AE84 wrapper, 7DCA outer, D22C launcher;
  - checker **`6318895035B8FC5C7D98215EDCCB5BDF987CE82596307EBAB5F0F553A0E179CC`**;
  - EXPECTED **`795AFC6F924EC7E6BCA8A330B9FA84632C572DBAB2CDEF61A44FB9240A7648C7`**;
  - OUTER **`D89A42FF2A36D2866454A7E3A6CF6F42973CA07474C48B37D0AE56E4FE0596B8`**;
  - VERIFICATION **`B6F944606D86794B6138BCB6546E0DFD2B7B2CA9AAFAC4954C6453F75FCC70E3`** (28 packet pins and 10 runtime pins, all re-verified; both false).
  - Manifest **`4C556393A0E369E43B0E4CF104F2FDABDD68EF204299E20B8650FED6D3FDF294`** (31 entries).
- **Inventory: 13 controls, 57 nested predicates:**
  1. SUBJECT-PINS (22).
  2. RUNTIME-PROVENANCE (7).
  3. DIFF-REDERIVATION (5).
  4. PRESERVED-OUTSIDE-CHANGE (4 exact partitions).
  5. SERIALIZER-DEFAULT-REGRESSION (4): source and candidate wire are byte-identical for every existing send step in the catalog and the MS NONEXPIRED and REFRESH inventories; the only changed script is the T05 close-delimited one.
  6. CLOSE-DELIMITED-SERIALIZATION (3).
  7. INVALID-MODE-REFUSALS (5).
  8. CLIENT-COMPLETENESS-VS-DECODE (4), on the actual transport and policy over the host `http.client` with the exact serializer bytes: close-delimited accepted; short-CL gives `IncompleteRead` before decode; close-delimited invalid JSON gives `JSONDecodeError` at decode (not framing); a transport error propagates unchanged.
  9. OUTCOME-CLASSIFIER (7).
  10. RUNNER-WIRING (5).
  11. BATCH-CONFIG (3).
  12. PRIOR-FAKE-APPLICABILITY (3).
  13. ACTUAL-SOURCE-MUTANTS (6, targeted prefixes).
- **Held fake command:** `Future-Command-HELD.ps1.txt` `00ED1BBD…E2A1` → `…\scheduler-native-t05-fake-prep-matt-v1\packet\Invoke-Fake.ps1 -AdmissionSHA256 B6F94460…`. `Launch-Decision.md` is `D2125893…C30A`.
- **Claims that no longer transfer** (each with its current prerequisite):
  - peer-close fake PRESERVED ("only `_close_connection` differs");
  - MS-refresh fake v2 OAUTH-ROUTE-TABLE (it executed the old serializer);
  - MS-refresh fake v2 transcript-derived controls (`ExchangeStep` gained a field);
  - the merge fake's peer row `17EA148E` (for this root).
  - The prerequisites are SERIALIZER-DEFAULT-REGRESSION, step-field equality and `transcript_functions_identical`.

## 3. Requirement-to-evidence applicability and open gaps
| T05 planning ID | this increment | status |
|---|---|---|
| T05-SHORT-LENGTH-VALID-JSON | ORDERLY (b) native body (held); fake controls 5, 8, 9 | **evidence candidate, held**; nothing native yet |
| T05-VALID-COMPLETE-CONTENT-LENGTH | the declared oracle mapping points at the close-delimited accept (see decision D1) | **open**; a close-delimited accept is not CL-complete evidence |
| T05-SHORT-LENGTH-INVALID-JSON | T05 combined-witness host fake (pending with Trish); this fake's control 8 shows decode-versus-framing on the serializer bytes | **open natively** |
| T05-MALFORMED-JSON | control 8 shows complete invalid JSON reaches decode (host) | **open natively** |
| T05-VALID-COMPLETE-CHUNKED, T05-CHUNK-EOF, T05-TE-CHUNKED-PLUS-CL, T05-TE-NONEXACT-PLUS-CL | none: the serializer refuses TE; no chunk mode | **open** |
| T05-DUPLICATE-CONTENT-LENGTH, T05-CONFLICTING-CONTENT-LENGTH, T05-MALFORMED-HEADER, T05-ENCODING, T05-NONOBJECT | none in this increment | **open** |
| (supplementary) complete close-delimited positive after orderly close | ORDERLY (a) native body (held); controls 6, 8 | evidence candidate, held |
| (supplementary) abrupt TLS truncation distinct from malformed/short/ASGI disconnect | ABRUPT native body (held); controls 8, 9 | evidence candidate, held |

**No full T05 or family closure.**

## 4. Decisions for you (not acted on)
- **D1, declaration mapping:** the existing NP-T05-ORDERLY-CLOSE oracle `orderly_close_delimited_complete_accepted` has `planning_ids=("T05-VALID-COMPLETE-CONTENT-LENGTH",)`. A close-delimited acceptance doesn't evidence Content-Length completeness. The fix belongs in the suite declarations, which I kept unchanged per the instructions to keep the 31 declarations. Options:
  1. remap that oracle to a close-delimited requirement (none exists among the 13 IDs);
  2. add a separate fixed-length complete observation to ORDERLY;
  3. leave it as is with this recorded gap.
- **D2, runtime check:** the abrupt class set (`SSLEOFError` or `ConnectionResetError`) is source-derived. If native shows a different transport-EOF class, the run STOPs (fail closed), and a narrowly reviewed widening would be needed.

## 5. Self-review notes
- **Root-path repoint:** my first `sed` didn't match because of backslash escaping. I caught it by counting, redid it as a root-name replacement, and confirmed 0 old and 3/7 new references with a clean JSON lint.
- **Retirement anchor:** `retirement = peer.retire_owned(join_seconds=5.0)` isn't unique in the runner (the earlier bodies have it too). The wiring oracle and its mutants therefore operate on the extracted `_t05_observe` segment, where it's unique.
- **Other anchors:** all read statically as unique; the bracket scan ends at depth 0.

## 6. Preservation
All verify at 0 mismatches:
- the MS-merge NONEXPIRED and REFRESH roots and both merge fakes (source and Dex staging);
- the peer-close staging and fake;
- the T05 combined-witness fake;
- the new T05 root.

The peer-close, T05 witness and merge-fake decisions remain separately pending. The endpoint is unbound, and all other holds stay.

Signed: Matt
