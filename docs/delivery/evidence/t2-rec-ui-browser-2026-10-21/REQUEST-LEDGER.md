# T2-REC-UI observed request ledger — 2026-10-21

**Runner:** Renee.

**Capture:** in-page `fetch` wrapper on Vite `http://127.0.0.1:5174` (proxy to API `http://127.0.0.1:18081`). Auth omitted. Bindings recorded by presence, not pasted (HMAC material).

**Stack:** Vite `:5174` → API `:18081` → Postgres `theplan_s1_test` `:5433`. Nebula disposable user. **Not** `:8000`.

## Recover / held calls (this session)

| t (UTC) | Method | Path | Request (exact or keys) | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 02:43:16 | POST | `/api/v1/schedule/held-misses/7dac39ef-3bc2-4eeb-9b3e-4bf7c0938ced/recover/review` | `{"disposition_id":"8f7a5537-756b-478c-8c5f-492235ed52b9","expected_revision":57}` | **200** | Open Recover. `review_ok_for_authorize: true`. Duplicate identical POST at the same timestamp (second 200). |
| 02:43:55 | POST | same `…/recover/review` | `{"disposition_id":"8f7a5537-756b-478c-8c5f-492235ed52b9","expected_revision":57,"catch_up_remaining_minutes":45}` | **200** | Refresh after remaining edit. `review_ok` true. |
| 02:44:26 | POST | `…/7dac39ef-…/recover` | keys only: `disposition_id`, `expected_revision`, `review_binding`, `authorize_instant` | **422** | `REVIEW_BINDING_MISMATCH` / “Recovery review binding intent mismatch”. Remaining **45 not in the authorize body**. No second authorize POST. |
| 02:48:09 | POST | same happy `…/recover/review` | `{"disposition_id":"8f7a5537-756b-478c-8c5f-492235ed52b9","expected_revision":57}` | **200** | Fresh open, no remaining edit. Duplicate identical POST, both 200, `review_ok` true. |
| 02:48:17 | POST | `…/7dac39ef-…/recover` | keys: `disposition_id`, `expected_revision`, `review_binding`, `authorize_instant` | **200** | `catch_up_task_id` `e2cf82d9-3805-4790-9916-8ec9a4888294`. One POST. |
| 02:50:03 | POST | `/api/v1/schedule/held-misses/532fd950-e8d3-48c7-9d8e-2f4753a4ce83/recover/review` | `{"disposition_id":"db7df4be-c50b-462a-a8d1-4405e6102fcb","expected_revision":58}` | **200** | C2. `review_ok_for_authorize: false`. `c2.code` `BLOCKS_PREVENT_NEXT_NORMAL`. Duplicate identical POST, both 200. **No** `…/recover` authorize for this task. |

`expected_revision` 57 → 58 matches the successful authorize (one bump). C2 review used 58.

## R3 re-run after `15ef355` (same ports, not `:8000`)

Task `REC-UI-r3 remaining` `7fb93de0-4a87-4660-8ddd-ed050cf7d8c8`, disposition `0e847af2-a84d-407c-9342-197209479dab`.

| t (UTC) | Method | Path | Request | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 02:59:35 | POST | `…/7fb93de0-…/recover/review` | `{"disposition_id":"0e847af2-a84d-407c-9342-197209479dab","expected_revision":59,"catch_up_remaining_minutes":45}` | **200** | Refresh after remaining edit. |
| 02:59:44 | POST | `…/7fb93de0-…/recover` | `disposition_id`, `expected_revision` **59**, `review_binding` (len 1229), `authorize_instant` `2026-10-22T02:59:35.587573Z`, **`catch_up_remaining_minutes`: 45** | **200** | `catch_up_task_id` `ce1e6338-bbdb-4e00-b984-b5854a095f6a`. Not `REVIEW_BINDING_MISMATCH`. |

DB read-back: disposition `recovered`; catch-up title `REC-UI-r3 remaining (catch-up)`; **remaining 45**; series due `2026-10-27 02:00:00+00:00`.

## Negative scan

Resource URLs under `/api/v1` included reads (`auth/me`, tasks, settings, `schedule/held-misses`, `schedule/runs?limit=1`, calendar events/conflicts, scheduled-blocks). **No** `/replan`, **no** preview apply, **no** provider/sync mutate, **no** task PATCH in the captured resource list. C2 copy offered no delete/unpin/manual-clear.

## DB read-back (same disposable DB, after the 200)

| Row | Result |
| --- | --- |
| Happy disposition `8f7a5537-…` | `recovered` |
| Catch-up `e2cf82d9-…` | title `REC-UI-happy weekly (catch-up)`, remaining 60 |
| Series due | `2026-10-27 02:00:00+00:00` |
| C2 disposition `db7df4be-…` | `unresolved_held` |
