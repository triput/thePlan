# Native NP-V-GOOGLE-REFRESH preparation v2 (HELD)

Matt, November 13, 2026. This is for Dex `CEBD83C3…6570`, with the in-task feedback `3E5590C4` (source pointers), `55B75EA0` (primary seed) and `F04CEFCA` (revision/busy), under lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED.
- Nothing was imported, parsed, compiled, tested or run.
- **Current documents:** this README, `Google-Refresh-Prep-Freeze.json` and `Google-Refresh-Native-Command-HELD.ps1.txt`. Everything else copied is history.
- **Source:** the passed NONEXPIRED retirement v2 (`C62FDA91`, 301 inputs, re-verified). Manifest-listed inputs only were copied; its evidence was not copied.
- **v1 (`scheduler-native-google-refresh-prep-matt-v1`, parent `06703C09`) is preserved untouched as partial work.** It was frozen before the primary/revision feedback was read, and it has no primary row, calendarList or revision/busy check.

## Changes
- **Role 8, transcript (additive):**
  - Google refreshed and rotated synthetic constants;
  - `google_token_refresh_success_script`;
  - `google_calendar_list_script`: exact `maxResults=250` query, one page, exactly one `primary:true` entry;
  - `google_busy_event`;
  - `google_events_one_page_script`;
  - `google_refresh_connection_inventory`: exactly **4** exchanges, in the order token, calendarList, events(canonical), events(informational).
- **Role 4, runner (additive):**
  - `_google_provider_routes`: exact oauth `/token`, exact identity `/calendar/v3/users/me/calendarList`, and the event prefix;
  - `_google_calendar_list_exact_query`;
  - `_google_events_exact_query`;
  - `_measure_google_credential_state`, `_measure_google_events` and `_measure_google_subscriptions`;
  - `_measure_owner_revision_and_busy`: `UserSettings.scheduling_revision` plus the production `immovable_busy_signature`, reduced to a count and a 16-hex digest;
  - `_install_google_parent_observer`;
  - `_run_np_v_google_refresh`, plus the implemented set and the mapper.
- **Case body, setup only:** the first str-sorted requested row becomes `role=primary` with `external_calendar_id="primary"`, checked against production `GOOGLE_PRIMARY_ALIAS`. The second row stays stable and informational. The canonical `np-google-canonical-primary` is checked as unoccupied, and the seeded map is kept truthful.
- **Assertions:**
  - only the primary row is rewritten, to the canonical ID (role and enabled unchanged);
  - `preflight_effects` is `["canonicalize_identity"]` on target 1 and `[]` on target 2;
  - the persisted owner revision rises and the busy signature changes;
  - the public `scheduling_revision_at_start` equals the persisted before revision, and `scheduling_revision_at_end`, `scheduling_readiness.scheduling_revision` and the persisted after revision are all equal;
  - `scheduling_revision_bumped` is true;
  - the unrelated owner's revision, busy signature, subscriptions, credential, coverage and events are unchanged.
- **Role 5, suite:** implementation note only.
- **Data:** runner-config and launch-config (CRLF kept), with gates false, a single-case batch, a truthful note and v2 own-root paths; docker-ops 7-path root rename.
- **Unchanged:** `np_auth_seed`, routes, peer `17EA148E`, PKI, sanitizer `69F59AF1`, all 234 application files, the operator and the helpers.
