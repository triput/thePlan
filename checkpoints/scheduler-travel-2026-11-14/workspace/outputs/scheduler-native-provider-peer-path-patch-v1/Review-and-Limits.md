# Peer exact transcript path: unexecuted source contribution

Candidate based on frozen prep-v3 np_provider_peer, without editing Jim's active successor. Only request-path comparison and per-exchange observations change. Production URL routing, TLS, socket operations, timeouts, terminal behavior and retirement are unchanged.

The peer now compares the raw path component exactly. An expected /v1.0/me/calendar cannot accept /v1.0/me/calendars/{id}/calendarView. If the script explicitly includes a question mark, the actual query must be present and match its exact wire spelling. Otherwise query strings are outside this script's comparison scope. This allows existing query-bearing owning calls while refusing prefix collisions; it is not complete query-contract proof.

The exchange inventory records method/path parsed from the actual request buffer, rather than echoing the expected script. It records query_present and query_verified booleans without retaining query values. Query-free scripts truthfully report query_verified=false. Jim should supply explicit expected queries from the planned window and selected owning-call parameters when claiming query correctness, rather than treating this patch as that evidence.

Integrate/adapt in the fresh successor and update pins. Add extracted peer-method fake checks for identity/event prefix collision refusal, exact path with query admission, exact declared query equality and mismatch, and actual observed inventory. Use memory-only buffers/stop flags; no sockets. Check code and any invocation remain separately held. No tests, imports, compilation, certificate generation or socket operations were performed for this contribution.
