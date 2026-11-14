# D2/T01 proposal v1 — independent static review

Reviewer: Dex. Status: REVISE before source-change approval. No implementation or execution.

Subject: Jim's docs-only `post-native-d2-t01-source-prep-proposal-jim-v1-2026-11-11`, TIP SHA256 E6CB1A4201294427F45E5546E7DDAC6EEE106123B5AD79C8A80E9BF8F08CE385; unapplied diff SHA256 08D0AE38C63F6579DED252549C439215CA35988BE1D0625D4A843550FF25078B.

All 23 independently checked pins match: nine proposal artifacts, six controlling policy/review inputs, three starting source files and five caller/inventory sources. See D2-T01-Proposal-v1-Pin-Reconciliation.json. Prospective amended-source hashes have not been independently reconstructed; this review does not accept those hashes as verified. No proposed Python code was imported, run or applied.

## Findings requiring a revised proposal

1. **The fixed two-pass inspection does not establish the approved nested-routing refusal.** Static trace of an opaque segment `foo%25252Fbar`: the first decode yields `foo%252Fbar`; the second yields `foo%2Fbar`. Neither the first-pass checks nor the second-pass slash/dot check rejects it. Likewise, deeper encoded whole-segment dot navigation is not covered. This is a source-supported gap in the proposed local admission policy, not a claim about actual provider normalization. Revise the proposed bounded inspection rule and enumerate deeper nesting and the depth/work-exhaustion refusal. Preserve benign `plain%25id`, encoded plus/@/=, original wire bytes, and opaque query data. Do not impose a blanket percent ban.

2. **Segment-role grammar remains unspecified in operational terms.** The proposed structural and opaque validators have identical bodies. The `calendars`/`events` name heuristic therefore does not establish which structural spellings are accepted, where IDs may occur, or how unsupported shapes fail closed. Do not infer a need to replace existing origin/purpose/route authorization with a new universal provider endpoint allowlist. Instead show the exact grammar needed at these two seams, its relationship to reviewed route prefixes, and the unchanged target-authorization boundary. Include identity/list and OAuth paths, supported calendarView/delta routes, and representative event-ID callers where relevant. Inventory which callers are in the covering refresh path versus other provider operations.

3. **The control inventory is not ready to freeze.** Several of the 21 rows are descriptions rather than exact inputs, including exact-prefix/child, duplicate mappings, continuation and target authorization. Expand concrete URL/method/purpose/profile inputs, expected exception class or successful result, opens/sends and retirement outcomes. Include percent-case variants, nesting beyond two passes, malformed/truncated encodings, raw/encoded dot navigation, empty/trailing segments and positive internal dots. Preserve the foreign-continuation 0-exchange versus allowed-3xx 1-original/0-follow-up distinction. Keep target authorization a separate oracle. A predicate-only check cannot establish builder/context/HTTP composition.

4. **Scope text contains unaccepted workflow and stale assignment references.** Remove or reconcile the proposed Renee/Page phase chain and the C06 offline-trace assignment claim. Jim is implementation lead; Dex owns design/review/integration, and Jim's sole current assignment is the independent offline native-v4 receipt review. No new mandatory reviewer or delivery role has been accepted. The future source-change card must pin an exact successor diff and scope; “or a reviewed successor with identical outcomes” must not become open-ended apply authority.

## Reconciliation of U1–U6

- U1: event-ID scope needs a caller inventory and explicit recommendation before deciding whether extending the disclosed compatibility restriction requires Trish's call. Do not silently apply a calendar-ID-only decision to unrelated operations.
- U2: malformed and nested encoding must be concretely enumerated under the existing approved prerequisite. Recommend fail-closed ambiguous/malformed path representations with well-formed encoded literal percent positives. Exact compatibility implications remain for review; no new policy is adopted here.
- U3: inventory actual builder/continuation shapes first. Unsupported empty segments can be an implementation of the approved unsupported-grammar refusal; a newly discovered legitimate trailing-slash caller would need an explicit disposition.
- U4: internal dots such as `a%2Eb` do not themselves constitute whole-segment dot navigation. Recommend preserving them unless evidence identifies ambiguity. A broader restriction would need justification and disclosure.
- U5: distinct public refusal reasons are unnecessary. Retain the sanitized existing exception class and use fixture input/control IDs to distinguish negative cases. No new public error taxonomy is requested.
- U6: this is principally a design/review task for Dex and Jim, not automatically a product decision for Trish. Produce a concrete bounded grammar and caller evidence before escalating a compatibility choice.

None of these recommendations grants source-change or execution authority. The existing D2 compatibility decision remains controlling. T01–T08 proof obligations remain open and unchanged; T02 fake PASS does not close synthetic provider transport proof.

## Next action and ownership

Preserve the original proposal. Dex has completed this static review while Jim independently reviews native-v4 evidence. After that sole assignment is returned and reconciled, send the bounded docs-only revision request; do not create a second active Jim assignment now. The successor should remain unapplied and return exact diff, grammar/outcome table, prospective hash derivation, controls and a source-preparation scope suitable for Trish's card. No tests, imports, live checks, installation, PKI, Docker or native rerun. Endpoint remains unbound and all other holds stay.
