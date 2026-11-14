# D2/T01 caller scope — Dex design reconciliation

Static source review only. No source implementation, imports or execution. This narrows the proposed amendment to the accepted covering-refresh use case; it does not narrow T01–T08 proof requirements.

Source root: `outputs/scheduler-t02-fake-v1/packet/payload/workspace/apps/api`. The five original caller/source inventory pins and three amendment starting pins match the proposal. Additional inspected `app/services/calendar_alias_canonicalize.py` SHA256 A661FE9287E0BE086CCB070DF8F227D2449CA9B70303140A7E38B4015A71946F.

## Caller distinctions

| Operation | Frozen caller evidence | D2 preparation consequence |
|---|---|---|
| Google refresh collection | `covering_refresh_import.py:658` clears the targeted subscription cursor before `_pull_subscription_changes`; `google_calendar.py:841` full branch calls `list_calendar_events`, whose URL is `_calendar_events_base` at line 80. | Calendar-ID opaque slot is required. Full-refresh event collection GET and pageToken query handling remain in scope. |
| Microsoft refresh collection | `covering_refresh_import.py:689` calls Microsoft `_pull_subscription_changes`; `microsoft_calendar.py:1556` explicitly uses ordinary `calendarView`, not the cursor/delta path. | `/v1.0/me/calendars/{calendar-id}/calendarView` and admitted continuations are required. Preserve and inventory direct delta helper compatibility separately; do not silently claim that the ordinary refresh invokes it. |
| Identity prepare | `calendar_alias_canonicalize.py:158` calls Google `list_google_calendars`; Microsoft `_fetch_default_calendar` and `list_microsoft_calendars`. Microsoft default caller at line 996 requests `/v1.0/me/calendar`. | Do not omit identity/list routes. There is no calendar-ID slot in `/v1.0/me/calendars` itself. These paths must not be misclassified from a segment-name heuristic alone. |
| OAuth refresh | `covering_refresh_import.py:517` token unit delegates to provider `get_valid_access_token`; Google token constant is `/token`; Microsoft `_token_url` at line 113 builds `/{tenant}/oauth2/v2.0/token`. | Existing exact reviewed OAuth origin/path and POST purpose remain enforced. Tenant route text is configuration, not a newly authorized calendar/event ID. No profile bind is authorized. |
| Event mutation helpers | Google `patch_google_event` / `delete_google_event`, and Microsoft `patch_microsoft_event` / `delete_microsoft_event`, append the quoted event ID. They invoke PATCH/DELETE; `_CoveringClient` exposes only GET/POST and `CoveringHTTP.request` refuses methods other than GET/POST with the OAuth pairing rule. | The cited event-ID builders do not require adding event mutation support to this covering-refresh packet. Leave ordinary callers unchanged. Do not add PATCH/DELETE, event mutation route admission or credentials. Future support would need a separate accepted scope. |

This source trace resolves the current need behind U1 without asking Trish to authorize an unrelated operation. A synthetic descendant path control does not itself authorize an event mutation or establish legitimate refresh caller behavior. Exact endpoint grammar still needs a reviewed successor proposal; this note is not an endpoint allowlist implementation.

## Design guidance for the docs-only revision

- Preserve the existing separation of peer origin, route/purpose containment, path ambiguity refusal and authorized calendar target. Route containment alone is not authorization.
- Keep raw send target bytes unchanged and query tokens opaque. Never canonicalize and forward an ambiguous path.
- Replace fixed two-pass assumptions with a bounded, precisely described inspection rule. Show termination/work bound and fail-closed exhaustion, deeper encoded separators/dot navigation, case variants, and benign percent positives. Do not execute a candidate to derive examples under the current hold.
- Spell out malformed/truncated original path escapes, Unicode/UTF-8 handling and intermediate literal percent behavior. In particular, decoding `plain%25id` produces a literal percent that must not cause the approved positive to be rejected merely because that intermediate string is not another valid escaped wire path.
- Preserve internal opaque-ID dots unless a concrete ambiguity justifies an additional restriction. Keep public refusal sanitized; fixture IDs can distinguish refusal branches.
- Map exact representative current caller paths to structural and opaque positions, including identity and OAuth. Any additional compatibility restriction must be explicit before source preparation approval. Unsupported route forms must have an exact refusal disposition; do not replace the unbound profile with an ambient default.

Original v1 remains REVISE. Jim should return a fresh docs-only successor with an unapplied exact diff, concrete outcome table, controls, prospective hash derivation and bounded source-preparation scope. Dex will reconcile it and bring actual compatibility/source-change decisions to Trish. No implementation, test, import, socket, PKI, Docker or native launch authority is added.
