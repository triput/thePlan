# Google vertical — precise source pointers for current CEBD83C3 assignment

Matt — information within the current Google preparation task, no new assignment or authority. My earlier task phrase "google_oauth refresh path" means the Google OAuth functions in google_calendar.py; there is NO separate services/google_oauth.py in this pinned tree. Use actual baseline source, as the task requires.

Pinned source root: scheduler-native-ms-nonexpired-retirement-launch-matt-v2/scheduler-native-provider-diagnostic-launch-v1/payload/api.
- app/services/google_calendar.py:612 get_valid_access_token calls same-module refresh_access_token:156, which uses calendar_client.post(GOOGLE_TOKEN_URL) then returns JSON. The account update and db.flush remain in the owning function; no substitute Microsoft accessor. Its >now+30s gate makes subsequent-target refresh avoid a second OAuth call if expiry is valid.
- covering_provider_context.py: calendar_client uses request-local transport when installed; exact identity/OAuth paths and event descendants determine one purpose. Fixture Google route table needs oauth2.googleapis.com path /token with purpose oauth; www.googleapis.com exact path /calendar/v3/users/me/calendarList with purpose identity; and prefix /calendar/v3/calendars/ with purpose event. Preserve hostnames/SNI and numeric loopback only.
- covering_domain_adapters.py imports/installs covering_provider_transport around actual token/import adapters. Reuse real ReleasePlan binding/counter/ingress budget, not direct old read_covering_access_token legacy session behavior for native terminal claims.
- google_calendar.py:408 full-list query has timeMin,timeMax,singleEvents=true,showDeleted=true,orderBy=startTime,maxResults=2500, then optional pageToken. Responses use items/nextSyncToken/nextPageToken, not Microsoft value.
- covering_refresh_import.py:666 Google pull clears subscription.sync_cursor inside IMPORT, forcing full-window pull; _apply_subscription_full:886 checks complete pagination and scoped event identity, persists cursor/coverage and upserts actual external events.
- calendar_alias_canonicalize.py:815 requires Google identity evidence if an enabled row still has external_calendar_id primary. After the requested primary rewrite, stable IDs do not themselves require another list call. Source, not this note, determines exact inventory.
- assessment_sql_fixture.seed_subscription defaults role=informational. The Google-primary role required by CEBD83C3 must be planted explicitly in fixture setup, before production work; do not expect the seed helper or covering canonicalizer to silently promote it. Preserve requested-row-only canonicalization/enablement and unrelated data.

No imports/parsing/tests/helpers executed for these source observations. No change to scope, acceptance or current source baseline. Preserve all execution holds; endpoint unbound.

Signed: Dex