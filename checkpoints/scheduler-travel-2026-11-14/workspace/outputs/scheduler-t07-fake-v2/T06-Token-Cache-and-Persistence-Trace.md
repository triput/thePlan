# T06 token cache and persistence: offline caller trace

Dex, November 11, 2026. Source inspection only from the accepted253-file host packet; no imports/tests, source edits, network, credentials or execution. This note does not add a second Jim assignment or change the pending T07 launch card.

## Observed source path

Both Google and Microsoft get_valid_access_token first refuse a missing encrypted access token, normalize a naive expiry to UTC, and reuse/decrypt the cached access token when expiry exceeds now+30 seconds. An expired/near-expiry token without a refresh token raises its provider reauthorization ApiError. Otherwise both call their selected refresh_access_token function before updating account fields and flushing.

Google reads access_token, encrypts/assigns it, converts expires_in to int, derives expiry with a minimum60-second adjustment, optionally replaces the refresh token and flushes. Microsoft validates the token fields through _validated_oauth_token_fields first, then updates encrypted access/expiry and optional rotated refresh and flushes. Neither inspected get_valid_access_token function catches CoveringRootOutcomeUnknown; an HTTP cleanup UNKNOWN escapes before these post-response field assignments. This is source-derived sequencing, not execution proof.

The owning make_domain_ports.token closure snapshots the three token fields before refresh, catches only CoveringReauthorizationRequired as TokenRejected, compares fields to decide changed and calls its native terminal hook with COMMIT if changed or ROLLBACK otherwise. The expected acknowledgment is exact. An escaping UNKNOWN bypasses that known-result terminal choice; connector/session cleanup and public response mapping remain distinct evidence obligations. Ordinary ORM flush is not a native COMMIT acknowledgment.

## Required later distinctions

| Scenario | Required actual observations |
| --- | --- |
| Cached fresh token | No OAuth exchange; unchanged fields; exact known token-role retirement; later ordered work uses the admitted value. |
| Complete refresh with rotated refresh token | One bounded exchange; exact validated persisted field transition; native terminal acknowledgment; no duplicate refresh or terminal. |
| Complete refresh without rotated refresh token | Existing refresh retained; access/expiry change handled once; no invented rotation. |
| Possible send followed by missing/truncated response | No replay; no token persistence from a JSON prefix; UNKNOWN with actual caller/role retirement and later-work refusal. |
| Complete invalid_grant with confirmed local retirement | Known reauthorization refusal mapping through the actual token adapter and exact unchanged-field terminal; distinguish from missing local retirement. |
| Complete invalid_grant plus uncertain retirement | Provider response evidence retained but overall uncertainty remains; no ordinary known reauthorization success or later admission based on assumed cleanup. |
| Complete response followed by validation/encryption/flush/terminal failure | Preserve remote-exchange completion separately from uncertain local state; actual acknowledgment and quarantine evidence, not a blanket known policy failure or automatic retry. |
| Multiple targets sharing an account | Same request-wide counter/budget and current persisted token state; observe actual exchange count and no per-target reset. |

No raw token strings, account secrets or exception messages should enter evidence. Use synthetic values and field-change indicators/hashes as reviewed. A fake encryption/session/terminal result must remain labeled; it cannot stand in for native persistence evidence.

## Relationship to current proof

The held T07 fake v2 selected Google refresh_access_token and importer try/except controls are intentionally narrower than this complete token-cache/persistence chain. Their result, if later approved and passing, would not close these T06 obligations. T05 response-completeness witnesses must be composed before trusting a token-shaped or invalid_grant-shaped JSON prefix as a complete acknowledgment. Full transport inventory remains unchanged.

This trace identifies proof requirements, not a demonstrated runtime defect or authorization to repair token handling. Any correction proposal must preserve the no-retry, typed known-result/UNKNOWN and native terminal contracts and return through the applicable review gate.
