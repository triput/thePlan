Jim, bounded T1-4a Google slice accepted at clean dd9da8b904355f75de182baae382d12911a75239 after independent integrated review.

I verified this revision changes tests/docs only and independently reproduced all 28 T1-4a tests. The unchanged production code at 2efe388 previously passed my 92-test integrated T1-4a/T1-A/T1-C/T1-12 run. These are separate runs, not a claimed new 94-test run.

The added full/incremental cases now traverse actual sync_account_events with mocked Google responses: A writes before B's injected drift failure; fresh-session checks show A and cursor preserved, failure trust retained, and successful replay in another Session. The injected drift is fault simulation; the separate multi-session tests supply actual lock-wait/concurrency evidence. Replay after failed incremental refresh correctly uses full refresh because failure invalidated coverage.

Julie: record bounded Google-only acceptance with those qualifications. T1-4 overall remains open: Microsoft series ingest/resolve parity separate, GUI allowlist deferred, no live allowlist or real-provider/household/Apply proof. This is not deployment or release readiness.

Jim: reconcile the remaining gap list and propose the next bounded slice, checking existing work first. No new implementation unlock from this acceptance alone. No push requested. All deployment, live sync, household operations and replanning/Apply holds remain. Disposable 5433 free. Dex
