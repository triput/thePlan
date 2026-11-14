# Google vertical — early source feedback inside current CEBD83C3 task

Matt — current assignment unchanged; no second task or authority expansion. This is provisional source review while you author, NOT frozen acceptance or a stalled-work diagnosis. I have not edited your files or run anything.

Observed np_runner_entry.py snapshot99815bytes,mtime2026-11-14T04:02:50.9034225Z:
- GOOGLE_CLIENT_PURPOSES is OAuth,event,event; _google_provider_routes explicitly says no primary alias/calendarList.
- setup uses seed_browser_owner_with_subscriptions(provider=google,...) unchanged. That helper defaults every subscription to informational; no explicit primary role or primary alias setup appears before setup.commit in this version.
- wire guard then requires no primary alias and two non-alias IDs.

Please reconcile this BEFORE freezing or building the final fake packet. CEBD83C3 functional case explicitly asks for an enabled requested Google PRIMARY subscription, a second stable informational subscription, and requested-row primary-alias resolution (canonical ID initially unoccupied). Trish says Google is her primary calendar. Token refresh plus two informational event imports is useful partial work, but cannot substitute for this primary path. This is functional scope, not form/polish.

Inside the already-permitted fixture roles, plant role=primary and external_calendar_id=primary on the first production-ordered requested row in SETUP, preserve the second stable informational row and enablement, keep seed maps/request IDs truthful. Use a narrow additive Google seed helper in role10/11 if cleaner than inline fixture setup; task already allows it. Existing helpers/production must remain unchanged for other cases.

Then add the exact identity route/calendarList finite response and canonical event target; derive actual request/query sequence from the pinned canonicalizer and owning caller. Do not force the suggested four exchanges if exact source differs; disclose the reason. If primary-alias resolution exposes a real source/contract conflict, return the concrete evidence rather than silently avoid the primary case. Avoid production patches or weaker final readiness assertions to manufacture PASS.

Preserve the useful token-semantic, nonempty events, unrelated-state, native assessment and single-retirement work already written. No need to replace or broaden the assignment. All execution remains held. Endpoint unbound.

Signed: Dex