# Microsoft identity/event route overlap — offline finding

Dex, November 11, 2026. Read-only source inspection; no imports, tests, generated-code execution, sockets, provider calls or production edits. Jim retains the current T05 framing/custody/native-peer-review assignment. This is a later integration blocker to reconcile, not a second assignment or a launch request.

## Source chain

Inspected the accepted scheduler-t07-fake-v2/packet/payload/workspace/apps/api snapshot:

- calendar_alias_canonicalize.py, fetch_account_identity_evidence: Microsoft identity evidence calls _fetch_default_calendar and list_microsoft_calendars. Raw SHA256 A661FE9287E0BE086CCB070DF8F227D2449CA9B70303140A7E38B4015A71946F.
- microsoft_calendar.py: list_microsoft_calendars uses https://graph.microsoft.com/v1.0/me/calendars. The covering event-list path uses /v1.0/me/calendars/{quoted-calendar-id}/calendarView. Raw SHA256 6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF.
- covering_provider_context.py, _CoveringClient._request: all non-oauth routes admit both exact prefix equality and prefix + slash descendants; purposes are accumulated, and len(purposes) != 1 refuses. Raw SHA256 875FBF61A386D661A4DD70609162E41540500F10AD6AEDCACAF790701D693240.
- covering_http_transport.py repeats the same non-oauth descendant rule when selecting a route for the supplied purpose. Raw SHA256 E942BB43827364A9F20E36AAB604F031287FFF2B3F15BE5CFE48FDE9E81FF4BD.

The initial lookup used a nonexistent calendar_identity.py name; rg located the actual implementation in calendar_alias_canonicalize.py. No missing file was treated as evidence of absent behavior.

## Concrete source-derived witness

Consider one reviewed Graph peer, with identity prefix /v1.0/me/calendars and event prefix /v1.0/me/calendars/cal-fixture/calendarView. For the actual event URL, the identity prefix matches as an ancestor and the event prefix matches exactly. The client therefore accumulates identity and event and refuses before transport.request. This follows directly from the inspected predicates; no dynamic observation is claimed.

A single broad identity prefix is not a workaround: it would charge event exchanges to identity pages. Omitting the identity-list route would omit a required real caller when identity evidence is needed. Changing vendor URLs, bypassing calendar_client or using separate per-role request counters would fail to demonstrate the requested production composition. The proposed unchanged-origin local TLS topology therefore needs this routing boundary resolved before it can claim full Microsoft identity-plus-event coverage.

The singular default-calendar route /v1.0/me/calendar does not itself match /v1.0/me/calendars/... under the required slash-boundary predicate. The actual account-identity path does not call fetch_microsoft_email at /v1.0/me; that broader profile route need not be added to this covering fixture merely because the helper exists.

## Narrow correction options for later review

Preferred candidate for independent review: identity and oauth prefixes match exact paths; only event prefixes admit slash descendants. Apply the same rule at both client purpose selection and HTTP route selection. The required list/default identity endpoints have fixed paths; their normal query-token continuation remains the same path and is unaffected. This candidate must be reconciled against the complete intended identity continuation inventory before it is approved: a legitimate continuation using a distinct path would need its own explicit route or a separately reviewed representation. No new compatibility restriction is adopted here.

Alternative: choose the longest matching prefix before deciding purpose. This retains broader descendant behavior but introduces precedence semantics and requires explicit equal-length conflict and overlap rules. It is a broader design change than exact identity matching and is not silently adopted to make the fixture pass.

The final proposal needs exact source diff/hashes and independent review. Existing source-change and execution gates remain. Do not edit the T07 snapshot or any failed evidence.

## Required proof before accepting a correction

Freeze original and candidate controls for: actual Microsoft default/list/event URLs with one shared transport/counter; list query continuation; event query continuation; exact identity accounting versus event accounting; ambiguous same-path/different-purpose routes; unapproved descendants; no send on refusal; and no reset of request-wide ceilings. Preserve Google fixed list and event paths and the approved D2 encoded-ID/query behavior. Use actual owning identity/list/calendarView methods in the eventual native synthetic composition, not only a hand-written purpose classifier.

An original refusal witness is not a corrected PASS. Fake controls establish classifier/counter flow only; actual TLS, native identity mutation/assessment, deadline and retirement proof remain separately required. Full T01–T08 scope, prior evidence limitations and unbound endpoint remain unchanged.