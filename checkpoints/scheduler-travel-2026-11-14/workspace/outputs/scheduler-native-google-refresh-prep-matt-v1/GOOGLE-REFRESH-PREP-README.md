# Native NP-V-GOOGLE-REFRESH preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `Matt-thePlan-Scheduler-Google-First-Vertical-Preparation-2026-11-13.md` (`CEBD83C3…6570`), under lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED.
- Nothing was imported, parsed, compiled, tested or run.
- **Current documents:** this README, `Google-Refresh-Prep-Freeze.json` and `Google-Refresh-Native-Command-HELD.ps1.txt`. Everything else copied is history.
- **Source:** the passed NONEXPIRED retirement v2 (`C62FDA91`, 301 inputs). Manifest-listed inputs only were copied; its evidence was not copied.

## Changes
- **Role 8, transcript (additive):** Google refreshed and rotated synthetic constants; `google_token_refresh_success_script` (POST `/token`, 200, expires_in 3600, rotated refresh); `google_busy_event`; `google_events_one_page_script` (exact path and query, one non-empty page, no next tokens); `google_refresh_connection_inventory` (exactly 3 exchanges).
- **Role 4, runner (additive):**
  - `_google_provider_routes` (OAuth `/token` + event prefix; no identity route);
  - `_google_events_exact_query` (production `_iso_z` over the production effective window; params mirror `google_calendar.py` l.409–416);
  - `_measure_google_credential_state` (semantic decrypt);
  - `_measure_google_events`;
  - `_install_google_parent_observer` (restorable);
  - `_run_np_v_google_refresh`, plus the implemented set and the mapper.
- **Role 5, suite:** implementation note only.
- **Data:** runner-config and launch-config (CRLF kept), with gates false, the single-case batch, a truthful note and own-root paths; docker-ops root rename.
- **Unchanged:** `np_auth_seed`, routes, peer `17EA148E`, PKI, sanitizer `69F59AF1`, all 234 application files, the operator and the helpers.
