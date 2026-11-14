# T07 retirement correction — bounded preparation for approval

Dex, November 11, 2026. Recommendation: authorize Jim's fresh-copy three-file implementation and separate fake-only verification-packet authoring below. Preparation only. This approval is required by the existing source-change hold; it grants no execution or repairs to prior evidence.

## Reconciled proposal

Jim's frozen v3 design TIP is `94362F46EE6912A9A6F2A7CB64A673E51A2037D145A1FB70721F373FE2B7AA91`, in outputs/scheduler-t07-retirement-design-v3 and the corresponding immutable F:/DropFolder/pending handback. Exact unapplied diff SHA256: `8623F550F8B0BE9DFA00EBD8AD066768F22BE0750DC3DD635CF0A2F7A4CE7808`.

Dex verified 11 artifact rows, all declared source pins, strict JSON, all six hunk counts/old contexts/new offsets, and all three resulting hashes by reconstructing candidate text in memory only. No candidate source was written/imported/compiled/executed for this review. See T07-v3-Static-Diff-Reconciliation.json, SHA256 `6FE2938733F2A08DA0F03711B2D36A09CC1E9C630C304FDABA07BD8B05CAC0AC`.

The narrow change:

1. CoveringHTTP attempts response close and transport close independently. It captures only this invocation's primary and raises a new UNKNOWN on cleanup uncertainty, preserving explicit primary/cleanup references and earlier retirement occurrences without mutating the earlier exception.
2. JoinedTLS.open classifies its own close failure as UNKNOWN with primary/cleanup provenance. This covers R08, where closed=True makes the later outer close a no-op. There is no raw-close retry or change to close idempotence.
3. The importer pull exception handler re-raises UNKNOWN before its ordinary failed-import mapping. A deferred import avoids the identified top-level dependency cycle.

Resulting source hashes:

| API path | SHA256 |
| --- | --- |
| app/services/covering_http_transport.py | E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD |
| app/services/covering_joined_https.py | 2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B |
| app/services/covering_refresh_import.py | 84F50367BC91E0368437B4CD6E6FA5FAC9A77E42A270F00E8FF1EC62BB25C339 |

## Authorized work if approved

Jim remains primary implementation owner. Create a new workspace packet from the immutable 234-file API copy under outputs/scheduler-d2-fake-v1/packet/payload/workspace/apps/api. Apply only the exact reviewed three-file diff in that new copy, with the above resulting hashes. Preserve the source copy, D2 packet and pending D2 card, all T07 design predecessors and every prior run. Preserve the three original source files separately as pinned original witnesses. No additional production code edits or import/type refactor are included.

Author a separate held fake-only verification packet using extracted actual frozen functions/classes with coherent registered globals and fake owned byte/socket/response, clock, owner-ID and caller/role dependencies. No application/vendor package imports in the later fake checks. Proposed entry files are check_t07_retirement_fake.py, invoke_t07_fake.py and admit_outer.py plus non-executable manifests/oracles/review/command documents. Reuse the reviewed bounded launcher/outer pattern; disclose any executable-wrapper delta for independent review. Do not run any entry file during authoring.

Required original/candidate and mutation controls cover all R01–R12 design obligations, primary plus each/both cleanup failure provenance, inner open failure followed by no-op outer close, earlier-occurrence preservation, importer UNKNOWN escape, identity/OAuth/event caller classification, and no later target or assessment admission. Retain positive success and known-outcome controls. Include C-OUT-VE and C-OUT-UNK to exclude ambient caller-exception attribution/mutation. For any fake injected owner ID, terminal acknowledgment or retirement result, label its proof limit explicitly; no actual threads/sockets are authorized by this preparation or implied by fake controls.

The original-source contract-miss controls must be designated witnesses with exact expected observations; they must not turn arbitrary failures or unexpected UNKNOWN into a passing run. Preserve original/candidate distinctions, exact emitted order, missing/duplicate/reordered inventory rejection and mutation sensitivity. Define bounded, fixed-field sanitized evidence (classes/packet-owned labels only), with no raw messages, locals, SQL, credentials, URLs or provider bodies. Show the finite production provenance-boundary inventory and reject unexpected occurrence shapes in the future evidence verifier rather than silently truncating or overwriting them. Return the full named inventory; no arbitrary control-count ceiling is set here.

Return exact source diff, all source/payload/extraction/runtime pins, proposed control IDs and expected outcomes, prospective command and admission hashes, complete retirement/capture limits, and a clearly HELD verification packet. Later execution requires its own exact-hash card. Routine in-scope check-authoring corrections before that freeze do not require repeated preparation approval.

## Reconciliation of Jim's decision list

C-OUT-VE/C-OUT-UNK are necessary verification controls, not separate product choices. Append-only provenance is part of this exact source design and this single preparation approval. R11 complete invalid_grant plus uncertain retirement must stop UNKNOWN under the inherited uncertainty/no-later-admission contract; no new typed-success/continuation policy is introduced. Fake DB rollback cannot establish provider retirement. D2 execution and T07 preparation remain separate gates.

## Holds retained

No imports/tests, compilation, verification or execution; no real threads/sockets, PKI/certificate generation, provider traffic, database, Docker/native launch, dependency downloads/installation, builds, deployment, endpoint/profile binding or production changes. No retries, force, cleanup operations or repairs to failed runs. No changes to transaction guards, public result contracts, budgets, request-wide limits, TLS trust policy, ownership or no-retry behavior. Full T01–T08 proof remains required and incomplete.
