# T05 original outcome layering trace

Dex, November 11, 2026. Offline source inspection only; no imports, compilation, tests or invocation. This refines the review of Jim's approved original-characterization packet, without changing source, policy, scope or execution authority.

## Pinned source basis

Paths below are under outputs/scheduler-t07-fake-v2/packet/payload/workspace/apps/api/app/services/:

| File | Raw SHA256 |
| --- | --- |
| covering_http_transport.py | E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD |
| covering_provider_context.py | 875FBF61A386D661A4DD70609162E41540500F10AD6AEDCACAF790701D693240 |
| covering_refresh_import.py | 84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339 |
| covering_domain_adapters.py | BA82577E8CF4B27D4EDD5A1B9D31B35E87990A381B83E22D4DB2A4D89352A53C |

Actual host http/client.py SHA2563A752927A1257EDEBCABAD42CA9508AD532F91C15431755BFBE437A32AB13EB2 remains separate from eventual native parser provenance.

## Exception/output predicates must name the observation boundary

CoveringHTTP.request constructs the transport before its try. Inside the try it opens, sends, calls response.begin(), checks content encoding, reads bounded8192-byte parts, decodes JSON and requires an object. Lines124–135 preserve CoveringReauthorizationRequired, but remap every other exception to CoveringRootOutcomeUnknown if purpose is oauth and transport.sent is true. Finally independently closes response and transport; any close exception supersedes the ordinary outcome with a new provenance-bearing UNKNOWN. _CoveringClient delegates; it adds route/purpose selection but no exception mapping or implicit status check.

The following are source-derived predictions to freeze against exact inputs, not executed observations. Assume admitted route/purpose, successful open/send, transport.sent true, and clean retirement unless specifically stated.

| Stimulus/phase | Raw parser/decoding cause | Event or identity CoveringHTTP boundary | OAuth CoveringHTTP boundary |
| --- | --- | --- | --- |
| Complete framing, malformed JSON | JSONDecodeError at json.loads | JSONDecodeError propagates; not CoveringTransportRefused | UNKNOWN after send |
| Complete framing, JSON non-object | Explicit object guard | CoveringTransportRefused | UNKNOWN after send |
| Non-identity Content-Encoding | Explicit encoding guard before body loop | CoveringTransportRefused | UNKNOWN after send |
| Chunk short-data/short-separator parser failure | Host IncompleteRead for the applicable exact transcript | IncompleteRead propagates | UNKNOWN after send |
| Complete400 invalid_grant object | Typed OAuth interpretation, not parser failure | Response400 object unless an owning caller checks status | CoveringReauthorizationRequired, preserved by dedicated except |
| Complete>=400 other OAuth object | Explicit OAuth status/error interpretation | HTTP response object for these purposes; later caller mapping separate | UNKNOWN |
| Valid object with declared remaining CL bytes at EOF | Host bounded-read EOF does not itself require IncompleteRead | May expose response/object despite framing contract miss | May expose token-shaped success; invalid_grant400 may become typed reauth despite same framing miss |
| Any response/transport retirement failure | Independent finally block | New UNKNOWN with explicit primary/close provenance | New UNKNOWN with remapped invocation primary/close provenance |

Thus the design's shorthand F12a invalid JSON/non-object cannot use one exact exception oracle for both, and the same encoding or parser-failure transcript across purposes cannot require the same exposed exception. Keep the underlying source explanation and the exposed boundary distinct. Do not alter production code to make an original prediction pass.

The generic OAuth after-send remap uses raise-from-None. A top-level UNKNOWN class alone does not prove which lower-level framing error occurred; pair the exact raw transcript and pinned source trace with permitted parser evidence/instrumentation in the existing driver. Do not label a manufactured lower-layer exception as independently observed. The ordinary finally path retains no extra diagnostic primary unless cleanup itself fails.

## Owning caller and terminal boundaries

covering_refresh_import.py lines968–1000 catches Exception from _pull_provider. It rethrows CoveringRootOutcomeUnknown unchanged, while other exceptions produce an ImportCoveringCacheResult with outcome failed, rollback_required true and needs_failure_unit true. This is an import instruction, not an acknowledged database rollback and not by itself a typed public known-failure result. Native terminal evidence is a separate obligation.

make_domain_ports.token catches only CoveringReauthorizationRequired to produce TokenRejected; if normal completion reaches the terminal hook, it requires exactly COMMIT_ACKNOWLEDGED when credential columns changed or ROLLBACK_ACKNOWLEDGED otherwise. An after-send UNKNOWN escapes that dedicated reauth catch. A fake Google refresh function alone does not prove these full token/terminal effects.

make_domain_ports.apply invokes the importer under covering_provider_transport; the actual context selects _CoveringClient. Outside that context calendar_client chooses ordinary httpx.Client, which is a different execution path. Status handling by an actual vendor caller is a fourth layer beyond raw parser, CoveringHTTP and _CoveringClient. State which exact layer each result comes from.

## Handback acceptance consequence

Expand per-purpose variants with exact distinct predicates and named observation boundaries. Preserve original miss observations, caller exposure, clean/failed retirement and terminal acknowledgment as separate evidence fields/limits. A finite witness can legitimately stop before a terminal; it cannot claim a later terminal happened. No new controls are declared executed and no remaining transport family is closed by this static trace.