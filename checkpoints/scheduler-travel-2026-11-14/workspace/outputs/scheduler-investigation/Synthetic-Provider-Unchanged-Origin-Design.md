# Synthetic provider composition with unchanged URL origins

Dex, November 11, 2026. Offline source/design investigation only. No fixture implementation, source edits, socket/PKI/Docker execution or topology authorization. Jim continues the one T05 fake preparation/peer-review assignment; do not interrupt it for this future design.

## Source evidence and implication

The accepted T07 snapshot's CoveringReleasePlan.for_request constructs CoveringHTTP from the plan's injected provider_routes. JoinedTLS then dials peer.address/peer.port numerically and verifies TLS with server_hostname=peer.hostname and peer.ca_file. HTTPSPeer.check_url compares the URL's host and effective port to that same hostname/port. There is no connect-port translation.

Verified raw source pins under scheduler-t07-fake-v2/packet/payload/workspace/apps/api/app/services:

- covering_release_plan.py:0265969CD230D42747CDB722D73FF2C8748144324B5B930E5EB940E97DC2B826
- covering_joined_https.py:2E6A4ABB0E9658747C07A06F17D4359987C926DDD3CFDC0FE098984922A6A29B
- google_calendar.py:8A33597198FEFBC8D5E6671D56FE4118091F89255A6F46A8589117127318231F
- microsoft_calendar.py:6A52B10FE43A7781718BAE0AC69DA91CA7FB3B48B9534EB18D5C9C80E75DD6EF

Thus a future synthetic peer can retain the actual vendor URL host/port while dialing127.0.0.1:443 inside the isolated fixture namespace. This is a source-supported topology candidate, not proof that port443 can currently be bound by the nonroot runner. Prior native receipts establish high-port gates and numeric transport; they do not establish effective low-port policy or a443 listener.

## Candidate route table — no binding now

| Unchanged URL host | Exact local dial | Candidate purposes/prefixes to freeze |
| --- | --- | --- |
| oauth2.googleapis.com | 127.0.0.1:443 | OAuth POST/token |
| www.googleapis.com | 127.0.0.1:443 | Identity/oauth2/v2/userinfo; calendar-list/calendar/v3/users/me/calendarList; events at the actual encoded calendar ID path |
| login.microsoftonline.com | 127.0.0.1:443 | OAuth POST at one fixed synthetic tenant/oauth2/v2.0/token |
| graph.microsoft.com | 127.0.0.1:443 | Identity/v1.0/me and calendar lists/default; event/calendarView at actual encoded calendar ID paths; actual approved continuation paths |

The actual fixed route prefixes must distinguish purpose unambiguously before a launch. Identity list versus exact identity query and event paths cannot share a broad prefix that changes _CoveringClient's purposes set. Real authorization/browser login routes are outside this goal; do not add accounts.google.com or authorize endpoints merely because constants exist.

One runner-owned loopback443 TLS listener can serve a fixed finite transcript script keyed by observed Host/path/method and expected exchange order, using a disposable fixture CA/server certificate with the exact synthetic-server SAN names. Do not resolve those hostnames or contact their public addresses. Use only synthetic tokens/account data. TLS hostname checking and CERT_REQUIRED stay enabled; wrong-name/wrong-CA cases deliberately supply distinct trust material. Keep provider and DB trust/private keys separate, with private fixture keys in approved runner tmpfs only.

## Unresolved low-port boundary

Nonroot low-port availability remains unestablished. Do not rely on an assumed Docker default, run a probe, add CAP_NET_BIND_SERVICE, set sysctls, switch user, change host firewall/port publication, or modify URL builders under this design note.

A later exact proposal must choose and disclose a viable isolated443 route. Candidate alternatives for review include an explicitly declared namespace-local unprivileged-port setting on the namespace-creating disposable container, or a narrower capability if justified. Neither is approved; the shared-network runner cannot silently change a DB-created namespace. If a restricted high-port profile is used instead, its real TLS/transport proof is useful but cannot be labeled unchanged full vendor-client composition. No rejected URL-builder path may be omitted from the accepted completion inventory to avoid this boundary.

## Required later proof and controls

- Freeze one owned listener, bounded concurrent accepted connections/workers, fixed fixture peer origins/numeric addresses/ports, finite request/response bytes and no unreviewed continuation. Observe actual URL-builder -> calendar_client context selection -> _CoveringClient -> CoveringHTTP -> JoinedTLS -> local TLS peer chain for selected Google/Microsoft paths. Distinguish each real method from injected DB/config/provider dependencies.
- Keep exact request-wide counters and production work210s/request240s/cumulative-cleanup30s budgets. No fresh deadline per request or byte/target. Real header/body/handshake/send stalls must record the actual first guard and bounded joined retirement; a supervisor timeout is not application deadline proof.
- Observe public/domain consequences through native acknowledged terminals where required: completed earlier targets remain, no later target/assessment after UNKNOWN, no retry/replay or token-success claim from incomplete acknowledgment. A successful DB rollback does not establish provider retirement.
- DNS/proxy/alternate-origin fallback must be absent/guarded and observable without replacing actual TLS/socket behavior. Foreign continuation refusal and original3xx response/no followup need separate exchange counts. Audit/instrumentation seams must be declared; source unchanged does not mean uninstrumented.
- Align finite framing variants with the T05 original/native-source evidence before proposing corrections. Keep original miss characterization separate from corrected acceptance. Preserve valid complete fixed-length/chunked-extension/trailer and orderly close-delimited positives.
- Reuse the pinned two-container/native fixture resource boundaries only through a new reviewed launch. All listener/worker/PKI children, source/runtime pins, identity/mount/isolation declarations, exact-ID cleanup and timeout limits must be complete in that packet. Existing passed containers were removed and cannot be reused.

No product decision or launch card is ready from this design alone. It identifies how the full accepted composition requirement could be demonstrated without changing vendor URL construction, and the exact topology gate that remains. Full76-ID transport scope and supplementary variants stay intact. Endpoint unbound; all other holds remain.