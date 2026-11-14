# Subset-safe first-vertical alias stimulus

Source-derived fixture design reference, not execution evidence or a new scope requirement. Use within the existing first-vertical assignment if helpful; preserve all production guards and ordered-result assertions.

The selected _preflight_load_targets sorts subscription IDs by str. classify_covering_prepare_mutation permits a requested-row identity rewrite, but refuses any change to another subscription or account membership. account_needs_live_identity_evidence fetches Microsoft identity only while an enabled external calendar ID is `primary`.

Consequently, placing the alias on the later-sorted row causes the earlier stable target's account-wide canonicalization to touch a sibling. That intentionally trips subset safety; it does not prove the successful vertical. Avoid changing the guard to accommodate that fixture.

One suitable two-row arrangement is:

| Planted/request order | Subscription ID sort position | Initial external calendar ID | Provider canonical ID |
| --- | --- | --- | --- |
| first | higher UUID (suffix1) | cal-np-other | cal-np-other |
| second | lower UUID (suffix0) | primary | cal-ms-default |

Keep the planted/request IDs inverted as already intended, but make the actual first sorted target the alias. The default response returns cal-ms-default. The identity-list response contains cal-ms-default marked default and cal-np-other as nondefault. No row initially occupies cal-ms-default; no duplicate/disabled alias occupant is planted. Both requested rows retain role and enabled state, and the subscription ID set remains unchanged.

Derive the exact four-exchange sequence from selected callers and this mapping: default identity, calendar-list identity, calendarView for cal-ms-default, calendarView for cal-np-other. After the first target's successful requested-row rewrite, no enabled primary alias remains, so the second target should not fetch identity again. Zero OAuth exchanges remain required for nonexpired tokens. Build expected query spellings from the actual planned window/caller parameters rather than copying an invented query contract.

Record before/after external IDs and the returned identity-rewrite effect, alongside mapped coverage generations/windows/timestamps and final assessment. Let the actual source determine generation values; do not prelabel a merge/revision value that was never measured. Preserve source-defined sibling mutation refusal with a separate memory-only negative control if that branch is included in the fake packet; this reference does not require another native case.

Source references in the selected v4 application tree:

- app/services/covering_refresh.py:_preflight_load_targets (str-sorted IDs).
- app/services/covering_refresh_import.py:classify_covering_prepare_mutation (requested-only rewrite and sibling guard).
- app/services/calendar_alias_canonicalize.py:account_needs_live_identity_evidence and canonicalize_calendar_account (actual primary stimulus and rewrite).

No source changes to these application files, imports, compilation, tests, DB access or provider operations occurred in this review. Jim owns fixture implementation in the fresh successor.
