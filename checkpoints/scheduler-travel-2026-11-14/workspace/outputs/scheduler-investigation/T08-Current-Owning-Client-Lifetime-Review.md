# T08 current owning-provider client lifetime: static boundary

Dex, November11,2026. Read/hash-only follow-through on the earlier T08 context/ownership design. No source changes, application parsing/compilation/imports, threads, sockets, tests or helper invocation. This does not close T08.

## Current observations

The pinned Google/Microsoft modules contain16 textual with calendar_client(...) construction sites, listed in T08-Provider-Client-Construction-Sites.json. Not all belong to covering refresh: OAuth code exchange and event create/patch/delete are outside the requested covering-only read/refresh operation. Do not make those methods part of a new native fixture merely because this inventory includes them.

Selected owning refresh bodies and synchronous pagination/default-calendar bodies were read directly: Google refresh_access_token, _paginate_events, list_google_calendars; Microsoft refresh_access_token, _graph_collect (used by its list/event callers), _fetch_default_calendar. These open a scoped client and return decoded data/items/tokens, not that client. A bounded text search in both modules found no literal return client, yield client, copy_context, create_task or Thread( construction. This is a limited source observation, not a proof against all aliases, dynamically substituted code or future call sites.

The actual covering worker constructs the request release binding inside the joined AnyIO worker (abandon_on_cancel=False). make_domain_ports installs covering_provider_transport around synchronous token and import provider calls. Its finally reset is separate from _CoveringClient lifetime: the client stores a transport reference and has no independent post-scope lifetime or foreign-thread guard. JoinedTLS separately captures its constructing thread and guards check/close/reuse. These are distinct objects and distinct test contracts.

## Consequence for the bounded native proposal

- Demonstrate actual production context entry/reset and joined worker IDs for the supported synchronous provider path. A test that deliberately caches or transfers a private _CoveringClient is a separate characterization, not proof that the current owning path does so.
- Exercise accepted foreign-thread check/close and reuse contracts on the real per-exchange JoinedTLS with actual owned/joined threads, rather than expecting an unrelated wrapper to enforce a new lifetime policy.
- After a covering scope resets, test ordinary-client factory selection with a sentinel/fake factory; do not open an ordinary provider connection or call that intended outside-context selection a covering fallback defect.
- Keep nested/reset/exception/sequential request/counter witnesses and actual foreign-owner/no-mutation/owner-retirement evidence. This note does not substitute static reads for real context/thread/socket observations.
- No new wrapper restriction is justified by the inspected owning call sites alone. If the later proposal requires one, establish the actual reachable behavior and intended contract, then bring the concrete source/policy question rather than silently widening the repair.

Preserve all accepted T08 planning IDs and the historical CTX-ESCAPE-CHARACTERIZE question at its precise scope. Native fixture roles still need their concrete preparation gate. Jim's one active assignment remains the documents-only native implementation-scope proposal. Both verification launch cards remain held pending answers; endpoint unbound.

Construction-site inventory SHA256: 92D7121513110687CD882A84971DDCF423590662737FE6E13B25ADF9A070F93D.
