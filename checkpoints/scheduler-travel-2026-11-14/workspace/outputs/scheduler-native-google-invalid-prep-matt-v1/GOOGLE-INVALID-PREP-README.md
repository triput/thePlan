# Native NP-V-GOOGLE-INVALID preparation v1 (HELD)

Matt, November 13, 2026. This is for Dex `Matt-thePlan-Scheduler-Google-Invalid-Grant-Preparation-2026-11-13.md` (`5FA59395…C5B1`), under lane `389A00DD…7E2D`.

**Status:** PREPARED_NOT_EXECUTED.
- Nothing was imported, parsed, compiled, tested or run.
- **Current documents:** this README, `Google-Invalid-Prep-Freeze.json` and `Google-Invalid-Native-Command-HELD.ps1.txt`. Everything else copied is history.
- **Source:** the corrected Google v3 (`FC1DC3CB`, 309 inputs, re-verified). Manifest-listed inputs only were copied; no evidence was copied.

## Changes
- **Role 4, runner (additive only):**
  - constants: `GOOGLE_INVALID_CLIENT_PURPOSES`, `GOOGLE_INVALID_CLIENT_OUTCOMES`, `GOOGLE_INVALID_TOKEN_TERMINAL_SEQUENCE`, `GOOGLE_INVALID_ACTION_SUMMARY`, `GOOGLE_INVALID_PREFLIGHT_CODE`;
  - `_run_np_v_google_invalid`;
  - the implemented set and a mapper branch.
  
  The success and Microsoft bodies, and every existing helper, are byte-identical.
- **Role 5, suite:** implementation note only.
- **Role 8 transcript:** unchanged. The case reuses the existing `google_token_invalid_grant_script`, a complete 400 `{"error":"invalid_grant"}` that the serializer frames with Content-Length.
- **Data:** runner-config (`case_ids` = `[NP-V-GOOGLE-INVALID]`, `launch_ready` false), launch-config (single-case batch `np-v-google-invalid-single-case`, gates false, a truthful note, own-root paths), the docker-ops 7-path rename, and the dependent manifests.

## Case (source-derived; unexecuted)
1. **Seed:** an expired Google owner with exactly one requested subscription, planted in setup as the enabled primary-alias row (`role=primary`, `external_calendar_id="primary"`), plus an unrelated non-expired Google owner.
2. **Path:** production ingress, then dispatch, then the TOKEN role, then `google_calendar.get_valid_access_token` → `refresh_access_token`, then CoveringHTTP with default JoinedTLS and the shared budget. The OAuth POST receives the complete invalid_grant, and CoveringHTTP raises the exact `CoveringReauthorizationRequired` (covering_http_transport l.353–360).
3. **Rejection:** the adapter returns `TokenRejected(CALENDAR_ACCOUNT_DISCONNECTED)` with `changed=False` and requires a native `ROLLBACK_ACKNOWLEDGED` (covering_domain_adapters l.47–60). Dispatch adds a static preflight row and skips `run_target` (covering_domain_dispatch l.218–221): no IMPORT or PARENT, no calendarList, no events.
4. **Asserted:**
   - public 200, `no_op`, exactly one row (`preflight` / `preflight_rejected` / `CALENDAR_ACCOUNT_DISCONNECTED` / no effects / `cause` None / `upserted` 0);
   - summary 1/1/0/0/0;
   - the final assessment completes with `assessment_error` None, and `all_requested_covering_ok`, `freshness_requested.ok`, `freshness_all_enabled.ok` and `scheduling_ready` all false;
   - the revision at start, at end and in readiness equals the persisted, unchanged owner revision, and `bumped` is false;
   - client purposes are exactly one POST oauth, and the client outcome is exactly `CoveringReauthorizationRequired`;
   - TOKEN is exactly one rollback acknowledgement;
   - PARENT is empty, and no worker exception escapes;
   - credentials, expiry, coverage, the subscription row, events, revision and busy signature are unchanged, and the unrelated owner is unchanged across 5 areas;
   - the peer inventory is exactly 1 POST `/token` with orderly close and exact bytes; the peer is retired once, joined, with no worker error.
5. **Observers:**
   - all are installed **inside** the inner `try` (closing the install-window qualification from `333AA4A6`);
   - all are restored in the inner `finally`, with an identity guard (token terminal and HTTP constructor) before the evidence;
   - an identity-checked defensive restore runs in the outer `finally`.
6. **Retention:** the declared oracle `token_rejected_path_not_ms` contains "token", so the unchanged sanitizer drops it from the receipt. It is enforced in memory, and its evidence is retained under the allowlisted `token_terminal` and `covering_token_terminal` keys.

## Not proved
Every native behavior above, and the derived not-ready readiness state.
