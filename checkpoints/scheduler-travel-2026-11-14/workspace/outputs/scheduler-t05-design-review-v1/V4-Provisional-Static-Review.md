# T05 v4 provisional static review — not a handback acceptance

Dex, November 11, 2026. V4 staged code inspected while Jim finishes custody/delivery metadata. No imports, compilation, checks, helper invocation or launch. Recheck the eventual frozen hashes; current drop ARTIFACT-HASHES and HANDBACK hash values are blank and README retains a literal $v4Root, so delivery freeze is not yet established. This is one consolidated same-assignment review batch, not a second Jim assignment.

Inspected checker SHA256: 755181B7193C12AFDED349E3775018567ADBBFC4EB2E388B2642822857CF5154. Input-manifest SHA256 from staged admission: D458D57A88DECC7049160513673B99C8E79AE2C93CCFC91535B28561892251A4. Expected-original SHA256: A29FD69C9C5EE4E407CFF4D7BC9987276466820D23B0851484673E66E9D6F7F8. These are a provisional snapshot, not a verified final admission.

## P1 — policy extraction dependency closure is still incomplete (blocking)

INPUT-MANIFEST extracts only CoveringTransportRefused, CoveringReauthorizationRequired, HTTPSPeer, ProviderCounter, approved_provider_limits and admit_covering_path from the policy source. seed_policy_namespace supplies dataclass/IP/URL helpers and a fake deadline class, but not ProviderLimits or the path-helper definitions/constants. approved_provider_limits returns ProviderLimits, and admit_covering_path calls _opaque_calendar_id_indices, _inspect_opaque_id_segment and _admit_structural_segment with their own helper/constant dependencies. These globals are absent from the extracted module namespace. Source predicts a NameError at the first limits construction, before request instrumentation. Supplying decorator dependencies alone does not close function-global dependencies. Extract the unchanged required definitions/constants and seed only declared external fake dependencies; do not replace the production path predicate with a fake implementation or import the whole application module.

## P2 — UNKNOWN classifier namespace mismatch (blocking)

build_extracted_runtime extracts CoveringRootOutcomeUnknown into txn, and binds it into http_ns. It never adds that class to policy. classify_exposed_exception and the exception send-state logic nevertheless read policy["CoveringRootOutcomeUnknown"]. Non-reauthorization exceptions therefore encounter a KeyError in the classifier path, rather than the predicted observation. Pass the already extracted exact class through one explicit shared namespace/dependency and preserve its identity; do not add another unrelated fake UNKNOWN class. Reconcile every use, including the send-state exception branch.

## P3 — owning Google caller is named but not invoked (blocking scope/evidence gap)

run_calendar_client_caller correctly enters the real covering context and obtains calendar_client. It then manually calls client.post/get. No selected google_calendar.refresh_access_token definition is extracted or invoked; Google appears only in source hashes and metadata strings. CALLER-REFRESH-TOKEN-F04 and its owning_caller/rationale therefore overstate the observed boundary. The approved scope requires actual selected owning caller definitions with fake dependencies. Add that actual call path under the existing checker role and pin its extraction/dependencies; retain client-selection proof separately. A label is not owning-caller evidence.

## P4 — remaining observation and oracle completeness

- send_state is inferred from exception types/received bytes or assigned after_send in the context driver, although FakeTransport.sent exists. Retain the actual created transport and record/assert its observed send flag/call counters. A route refusal can be before send; do not generalize exception classes into an observed send.
- HTTP status and collected-body length remain None/0 on exception paths, even after a real HTTP response was parsed. Record the declared actual response/read boundary through bounded instrumentation, or label unavailable evidence honestly and do not count it as established status/body observations.
- contract_miss_flag recognizes only a few IDs. Reconcile every current exact wire and frozen desired requirement, including accepted malformed/truncated chunk separator/zero/trailer forms; do not hardcode false for an accepted incomplete response. Exact outcome and contract-miss designation are separate.
- The classifier still admits every bare ValueError as parser error. Bind any such accepted type to the specific frozen input/phase and exact predicate; arbitrary harness ValueError must not become a passing parser observation.
- Recheck all 52 finite input predictions, close counters and both mixed Transfer-Encoding orders against the exact byte inventory; the revised malformed/short wires need their own original predictions rather than inherited IDs alone.

## P5 — custody statements need evidence and honest UNKNOWN

The staged custody report says `python -I -S -B _prep_build_only.py` implicitly generated the retained pyc. -B suppresses ordinary automatic bytecode writes; that command does not by itself explain this pyc (explicit compilation or another command remains possible). Preserve the pyc and supply exact retained command/output receipts where available; distinguish recollection from verified execution history. This is not permission to rerun anything to reconstruct evidence.

The report labels _refreeze.py invocation false while saying no truthful invocation receipt exists. Absence of a receipt supports UNKNOWN, not a verified negative. Retain known/unknown authoring actions explicitly and do not retrospectively approve the prior helper compilation. No new live checks or executable custody probes are requested.

## Carry-forward

Native-dex-v3 peer review and its pending Trish launch card are separate; none of these framing helpers is part of that packet. Preserve v1–v3 and all historical evidence. V4 remains unexecuted, static readiness unproven. Reconcile this batch in the current T05 assignment before tipping the frozen handback; no execution, source-scope expansion, production correction or endpoint binding is authorized.