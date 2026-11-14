Jim, independent integrated run at 9fc9afa0b7e23f1d677e22b8878264e633cdccb5: 113 passed, zero skips across T1-D, T1-E Microsoft, Microsoft calendar, and T1-12; clean tree. The production context argument and uncertainty defaults are corrected.

One requested evidence boundary remains before residual acceptance: the new sync regression mocks list_calendar_view and covers only the normal missing-showAs control. The projected-omit case still injects context directly into _apply_subscription_full, and the continuation case does likewise. Please add a focused regression through sync_account_events with the real list_calendar_view/_graph_collect path and mocked HTTP pages: supply projected request params at the request-builder seam, assert those are the params actually sent, carry a nextLink page, then verify previously trusted free becomes unknown_projection and fails trust. Retain the normal unprojected control. No real Graph calls.

This is completion of the already requested production-route and continuation evidence, not another policy or mapping change. The current pull computes context from a separate invocation of the params builder, so the test should establish agreement with the actual request rather than assuming it. Return the evidence tip; no need to broaden into unrelated tests or new provider behavior. Holds remain; disposable 5433 is free.

Dex
