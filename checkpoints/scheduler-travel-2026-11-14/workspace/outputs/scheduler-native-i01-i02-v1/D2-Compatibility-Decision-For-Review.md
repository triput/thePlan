# D2 compatibility decision for Trish

Resumed by Trish on November 11, 2026. Policy-only decision; no implementation or execution is included.

## Recommendation

Approve the following explicit local covering-refresh path restrictions:

1. Allow at most eight successful percent-decode transitions while inspecting an opaque calendar-ID segment; refuse deeper representations. This may refuse otherwise harmless deeply encoded literal IDs. It bounds interpretation rather than claiming every rejected ID is malicious.
2. Decode inspected representations as strict UTF-8. Refuse invalid byte sequences instead of replacing them; continue admitting valid percent-encoded Unicode IDs such as `caf%C3%A9`.
3. Refuse malformed original-wire percent escapes, encoded structural path tokens, and empty/trailing path segments. Preserve approved encoded plus/@/=, internal non-navigation dots, benign literal percent (`plain%25id`) and opaque page-token query content.

Recommendation rationale: explicit decoding and bounded inspection make the accepted ambiguity refusal deterministic and testable. The caller inventory does not require percent-encoded structural tokens or trailing empty segments for the reviewed covering-refresh routes. These are compatibility restrictions, not evidence of provider normalization or a live exploit. A future legitimate caller outside these rules would require a reviewed disposition rather than normalize-and-forward or fallback.

## Evidence and scope

Jim corrected3 TIP 19E999AF6419BFA49C7DC9EDEEBB162F3BCE9793333EC62DD858E54F8C8FE5AE; ten artifact hashes match; forty unique named control rows are present. The unapplied proposed three-file diff remains byte-identical to corrected2, SHA256 CDB3AF210C7DD2BDC725F44F61931AD39B8010D5D259289D5D1FEF3E98E3F4F4. Fixed structural positions identify calendar-ID slots, so a literal ID `calendars` is not rescanned as a grammar marker. This is static source review, not behavioral verification. Corrected3 prospective source hashes still require exact independent reconstruction before a source-preparation card.

Approving this decision grants policy direction only. The source-change hold remains: a separate exact fresh-copy three-file scope must be reviewed before implementation. Tests/imports, fake verification, native launches, sockets, PKI, installation and deployment remain separately held. No endpoint/profile bind or actual provider operation is proposed. Existing transaction, result, budget, TLS, retirement and no-retry contracts remain unchanged.

## Routine oracle corrections before implementation/verification review

- Exact-prefix positive currently supplies a collection-prefix route but a longer events path, exercising descendant matching twice. The exact-match control must set prefix equal to its admitted full request path; keep the separate slash-boundary child control.
- The encoded-structural path negative must use a synthetic already-matching reviewed test prefix if it is intended to exercise the helper. An exact identity prefix would refuse the URL before the helper, proving a different branch.
- `_CoveringClient` lacks a `.patch` method; invoking it directly yields AttributeError, while `CoveringHTTP.request("PATCH",...)` performs the typed method refusal. Label each exact entry and outcome truthfully; do not add PATCH support or pretend the two entry points expose the same API.
- Forty descriptive rows are not full T01–T08 proof or a frozen executable inventory. Expand missing adversarial distinctions and retain the entire accepted transport matrix when authoring later fixtures. Preserve numeric address/public CA test pins and explicit byte/peer retirement assertions at fixture freeze; real provider hosts in docs are names only, never authority to dial them.

These are engineering reconciliation tasks within the existing docs-only lane, not additional policy questions for Trish. Jim remains implementation lead after the required source gate. Native-v4 proof and cleanup remain accepted; the integration goal remains incomplete.
