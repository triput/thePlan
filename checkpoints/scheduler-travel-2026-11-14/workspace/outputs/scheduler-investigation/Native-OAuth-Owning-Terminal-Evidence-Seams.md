# Native OAuth proof: owning-call and terminal seams

Dex, November11,2026. Offline source reads/hashes only. Design evidence for the later bounded native provider packet; no fixture source authoring or execution. Jim continues one active framing-v3 correction. Port verification card remains unanswered; no launch is authorized.

## Verified source flow

covering_refresh_import._refresh_provider_access_token dispatches to the actual Google or Microsoft get_valid_access_token. Both return the stored access token without OAuth when its expiry is more than30s ahead. The historical I01 seed sets expiry seven days ahead; that seed cannot prove a refresh exchange. New refresh cases must explicitly expire the disposable synthetic token and configure only synthetic OAuth settings. Existing fixture_settings supplies Google settings but no Microsoft client/secret/redirect settings; a Microsoft refresh case must explicitly supply those synthetic fields and the intended tenant (whose exact path is used by _token_url). Never use ambient settings or read a real client-secrets file.

The owning refresh_access_token implementations call calendar_client.post through the covering context. Google posts to its exact token URL; Microsoft builds /{tenant}/oauth2/v2.0/token and includes scopes. These are distinct owning definitions, even when the shared CoveringHTTP framing implementation is reused. Direct low-level OAuth POST observation is not a native owning-provider refresh proof.

On successful refresh, get_valid_access_token writes encrypted access/optional rotated-refresh token and expiry to the ORM account and flushes. make_domain_ports.token snapshots those fields, classifies changed versus unchanged, and calls the native covering_token_terminal hook under the existing locks. The hook must acknowledge COMMIT if changed or ROLLBACK otherwise. Native close_known checks that terminal and retires without duplicating it. Only after the TOKEN role returns does dispatch admit the parent event-import unit.

## Consequence for truthful fixture oracles

The token unit is separate from the later event-import unit. If token refresh has already reached acknowledged COMMIT, a subsequent known event-import rollback does not roll back the committed token refresh. Assert each unit's observed terminal and durable state separately. Do not require all token fields to revert merely because event import failed. This is existing source behavior, not a proposed transaction-policy change.

For ambiguous provider acknowledgment, absence of local token writes does not prove the provider did not rotate its token. The request can remain UNKNOWN while the observed disposable database retains old token fields. Keep provider ambiguity separate from durable local state.

## Exact outcome obligations to carry into the later packet

| Scenario | Required owning path and observable evidence | What it must not claim |
| --- | --- | --- |
| Nonexpired positive | Actual get_valid_access_token returns prior token, no OAuth request, native TOKEN rollback acknowledged; identity/event import and final assessment measured separately | OAuth success from a seed that skips refresh |
| Expired, complete successful Google acknowledgment | Real Google refresh_access_token through covering TLS; observed request and bounded complete response; changed account fields; native TOKEN commit acknowledged; subsequent import/final assessment state | Durability from flush or low-level HTTP result alone |
| Expired, complete successful Microsoft acknowledgment | Real Microsoft refresh_access_token plus _validated_oauth_token_fields; explicit synthetic Microsoft config/tenant; same distinct terminal/persistence obligations | Google proof as automatic proof of Microsoft caller/config/validation |
| Complete HTTP400 invalid_grant | Shared HTTP raises CoveringReauthorizationRequired; token port returns TokenRejected(CALENDAR_ACCOUNT_DISCONNECTED) only after acknowledged unchanged-unit rollback; parent skipped for that target; known-result/final-assessment behavior observed | Persistent account disable or token deletion: this catch does not perform either |
| Other OAuth error, malformed/truncated/lost acknowledgment after send | Existing after-send remapping to UNKNOWN; admission stops, no automatic replay, no later target or final assessment admission; observed local tokens and native resource disposition retained | Known reauthorization or known failure from unchanged local tokens, parser exception class alone, or fake empty receive |
| Successful TOKEN commit then later known event failure | Refreshed tokens remain committed; parent import rollback/result and assessment behavior separately recorded | Global rollback of the earlier token unit |
| Lost database terminal acknowledgment during token commit, if claimed | Distinct DB terminal fault and subsequent exact read-only state evidence; UNKNOWN regardless of whether server actually committed | Provider-ack truncation proof as an interchangeable database lost-COMMIT-ack proof |

These are source-derived evidence obligations, not executed outcomes or a frozen runnable case count. Preserve the accepted T06 IDs and reuse prior exact component evidence where it proves the property. Do not add a redundant full Cartesian provider/fault matrix merely because two callers share a lower-level implementation. Distinct owning calls/configuration and durable-state claims still need matching proof.

## UNKNOWN and known-refusal boundary

The inspected domain adapter catches CoveringReauthorizationRequired specifically and returns TokenRejected after terminal classification. For an uncertain exception escaping the TOKEN body, the role connector stops admission, attempts its existing quarantine path and raises UNKNOWN. Dispatch preserves already completed results but does not continue later targets/final assessment. An acknowledged invalid_grant preflight refusal is a different branch and can remain a known typed result. Do not require global stop for every classified target refusal or silently allow continuation after UNKNOWN.

## Later fixture design constraints

Observe disposable encrypted-token state through bounded comparisons/booleans or hashes; do not put token plaintext, client secrets, request authorization fields, SQL or raw provider error bodies into public receipts. Fixture-only sentinel values may be compared inside the owned disposable process. Use actual native terminal identities and commands, role sequence, peer exchange counts and final persisted assessment changes. Do not make an observer open additional application transactions after UNKNOWN; any post-fault read-only reconciliation must be a separately designed, declared diagnostic boundary consistent with the holds.

New native peer/PKI/case/supervisor roles remain outside the current fake authoring lane. A concrete preparation scope and separately reviewed launch are still required. No code change is proposed by this note. Endpoint unbound; no providers, real credentials, installation, deployment or expanded permissions.

Source pins: Native-OAuth-Owning-Terminal-Source-Pins.json, SHA256 2CBBD0B6CB50CABE680732FF3E6F88C7AC5FFDDB2B9FBF2D0D08DD9EB9634AE8.
