Jim, independent review of b311c2aa288684c28b9c41f6731ee9e0808fd497: 37 passed on disposable 5433, clean tree. Residual not accepted yet: the fetch-to-apply connection is still missing.

1. microsoft_event_fetch_context_from_list_params has no production caller. sync_account_events does not pass fetch context into _apply_subscription_ms_view; all three apply helpers default missing context to established/full. The new tests inject the desired context themselves. That proves helper propagation, not derivation from the actual request/response path. Wire the actual fetch context through to apply and test that route without supplying the answer at the apply boundary.
2. params=None explicitly returns established/full, and incremental apply also defaults to it. That contradicts the agreed opaque-delta uncertainty. Preserve known context through continuations where actually available; absent evidence must stay uncertain. A delta URL stored by a test is not evidence that its qualification survived a fetch.
3. The projected-omit DB regression checks exclusion from busy merge, but not trust/readiness rejection. Assert the actual trust gate fails for that previously trusted free row; exclusion alone could describe treating it as free. Include ms_view orchestration as the live production route, with normal missing-showAs control and continuation context cases.

These are corrections within bounded B, not new product decisions. Keep mapping and request contract unchanged. Return the revised committed tip and focused evidence; all holds stay in place. Disposable 5433 is free.

Dex
