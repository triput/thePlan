# Route overlap correction — design proposal, not implementation authority

Dex, November 11, 2026. Exact unapplied diff: Proposed-Fix.diff, SHA256 535FB0A3AFA576EB739042BDD72B707218E42D13D278E8C007B87083DC66D5A6. Proposal-Pins.json records original and prospective raw-byte source hashes. No application file or candidate copy has been written; no imports/tests or execution occurred.

## Proposed two-line correction

Only event routes accept slash-descendant path matching. Identity and OAuth routes require an exact path. Apply the condition once in _CoveringClient purpose selection and once in CoveringHTTP route selection. Keep the separate non-OAuth page-accounting condition unchanged. Do not add longest-prefix precedence, new routes, URL rewriting, counters, TLS behavior or retries.

This removes the identity-list ancestor match from a Microsoft calendarView request while preserving the exact list route and event descendant routes. Equal-path conflicting purposes still refuse. The original/candidate predictions require separate verification; this proposal is not executed proof.

## Continuation compatibility and decision boundary

Google list pagination reuses GOOGLE_CALENDAR_LIST_URL with a pageToken query parameter. Microsoft _graph_collect follows @odata.nextLink, makes root-relative links absolute under Graph, and clears the initial params on subsequent links. Same-path absolute/root-relative continuations with opaque query tokens are compatible with exact identity paths.

The inspected Microsoft caller does not guarantee that every future provider-returned continuation uses the same path. Exact identity matching would refuse a distinct descendant path that the old prefix rule could admit. Such a link needs its own explicit reviewed identity route or a different reviewed route representation. This is a disclosed compatibility restriction requiring Trish's policy decision; no claim about Microsoft's external service behavior is made from local source.

Before an approval card, independently review the actual covering identity/list/event URL inventory, the proposed compatibility restriction, and these source predictions. Jim's current T05 assignment must finish first; this proposal does not add a concurrent assignment. A later concrete source/check-authoring scope and exact run packet remain separately gated.

## Minimum original/candidate control inventory

| ID | Required original/candidate observation |
| --- | --- |
| ROUTE-MS-LIST | Exact Graph /v1.0/me/calendars selects identity; one identity admission, zero event admissions. |
| ROUTE-MS-EVENT-OVERLAP | List identity plus explicit calendarView event routes: original ambiguity refusal before transport; candidate event selection and event accounting. |
| ROUTE-MS-DEFAULT | Singular /v1.0/me/calendar selects identity and does not collide with plural calendars event paths. |
| ROUTE-MS-LIST-CONTINUATION | Actual _graph_collect with absolute and root-relative same-path query continuation preserves identity selection and shared counters; no duplicated initial params. |
| ROUTE-MS-EVENT-CONTINUATION | Actual calendarView collection with query continuation preserves event selection and shared counters. |
| ROUTE-IDENTITY-DESCENDANT | A distinct unlisted descendant is an original admitted-prefix witness and a candidate refusal; record the compatibility change explicitly. |
| ROUTE-EXPLICIT-SECOND-IDENTITY | A separately reviewed exact continuation path selects identity when explicitly listed, without admitting its unlisted descendants. |
| ROUTE-EQUAL-PATH-CONFLICT | Exact same path configured for different purposes refuses before send under both classifiers. |
| ROUTE-GOOGLE-LIST | Actual Google list caller, including pageToken query continuation, retains identity accounting. |
| ROUTE-GOOGLE-EVENT | Actual Google event URL builder/caller retains event accounting and approved encoded-ID/query admission. |
| ROUTE-OAUTH-EXACT | Google/Microsoft refresh POST exact paths select oauth; unlisted descendants refuse and no OAuth page counters are invented. |
| ROUTE-D2-PRESERVATION | Approved structural traversal/encoded-ID rules remain unchanged and run before allocation/send; do not derive corrected URL restrictions from this proposal. |
| ROUTE-REQUEST-SHARING | Identity and event exchanges share the original request-wide page/item/byte ceilings and deadline callback; no per-role/target reset. |
| ROUTE-SOURCE-INVENTORY | Original/candidate differ only by the two approved routing predicates; the non-OAuth page branch and every other application byte remain unchanged. |

The controls must invoke real extracted client/HTTP classifiers and selected owning provider methods with explicit fakes, not a copied handwritten classifier. Unexpected NameError/TypeError is a harness failure, not an accepted routing refusal. Actual native/TLS composition remains a later proof layer. These named controls are a minimum, not a cap on accepted T01–T08 obligations.

## Holds

No implementation or verification command is provided for invocation. Source changes require the reviewed preparation approval; any later fake/native launch requires exact commands, hashes, limits and explicit execution approval. Preserve T07 and all prior failed/successful evidence. Endpoint remains unbound; no live providers, credentials, installation, deployment or expanded access is included.