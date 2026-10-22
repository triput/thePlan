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

## Bounce re-run at `56dde72` (browser, not the seed probe)

**Runner:** Renee. Vite `:5174` → API `:18081`. In-page `fetch` wrapper. Bindings recorded as lengths only. Browser zone `America/Los_Angeles`.

Seed script also POSTed review once per new row before the browser opened. Those calls are **not** in this table. Browser calls only.

Happy task `1ec53c0e-7a53-4036-985c-1b0f20e87011`, disposition `b48129a8-46c1-4f57-8c73-8a9b82ec73fc`.

| t (UTC) | Method | Path tail | Request (keys / values, no binding secret) | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 03:18:43 | POST | `…/recover/review` | `disposition_id`, `expected_revision` 65 | **200** ×2 | Open. StrictMode pair. `review_ok` true. No catch-up fields. |
| 03:19:22 | POST | same review | due `2026-10-28T22:30:00.000Z`, deadline `2026-10-29T23:00:00.000Z`, remaining **45**, rev 65 | **200** | First refresh after editing due + deadline + remaining. |
| 03:19:38 | POST | same review | same due + deadline (server `Z` form) + remaining **45** | **200** | Second refresh, no further edits. Intent retained. |
| 03:19:59 | POST | same review | same due + deadline, remaining **50** | **200** | Only remaining changed. Dates retained. |
| 03:20:14 | POST | same review | same dates, remaining **50**, wrapper hold **3500ms** | **200** | **Applied.** Edit arrived after the hold. Not the discard. |
| 03:20:40 | POST | same review | same dates, remaining **77** | **200** | Rebound after that late edit. |
| 03:20:48 | POST | same review | same dates, remaining **77**, wrapper hold **1200ms** | **200** | **Discarded.** UI remaining stayed **88**. Review time stayed 03:20. Authorize stayed disabled. |
| — | — | — | catch-up due `2026-11-01T01:30` then `2026-03-08T02:30` | **no POST** | Client LA fold, then client LA gap. Alert only. Ledger length unchanged until the next row. |
| 03:22:06 | POST | same review | due + deadline as above, remaining **45** | **200** | Restored unambiguous due, refreshed. |
| 03:22:06 | POST | `…/recover` | due, deadline, remaining **45**, `authorize_instant` `2026-10-22T03:22:06.639543Z`, `review_binding` len **1393**, rev 65 | **200** | `catch_up_task_id` `9566f9a5-812a-4c3b-81b2-dc5c51a1fbd9`. |
| 03:22:52 | POST | fixed `936bb971-…/recover/review` | disposition `2304f320-…`, rev **66** | **200** ×2 | `successor` `FIXED_PAST_REQUIRES_CHOICE`. `review_ok` false. No authorize. |
| 03:23:12 | POST | fold `2dcc9ca1-…/recover/review` | disposition `39dd7674-…`, rev 66 | **422** ×2 | `BOUNDS_ROLL_INDETERMINATE_LOCAL`, `field=due_at`, `kind=fold`, wall `2026-11-01T01:30:00` LA. |
| 03:23:25 | POST | gap `c362b01a-…/recover/review` | disposition `49aa7806-…`, rev 66 | **422** ×2 | same code, `kind=gap`, wall `2026-03-08T02:30:00` LA. |

API access log on `:18081` for this browser session: **no** `PATCH`. No replan / preview / apply.

### DB read-back (`theplan_s1_test`, after the 200)

| Row | Result |
| --- | --- |
| Happy disposition | `recovered`; series due `2026-10-27 03:00:00+00` |
| Catch-up `9566f9a5-…` | title `REC-UI-happy weekly (catch-up)`; due `2026-10-28 22:30:00+00`; remaining **45** |
| Fixed / LA fold / LA gap / C2 | still `unresolved_held` |

## Bounce2 at `2b290eb` (browser, not the seed probe)

**Runner:** Renee. Vite `:5174` → API `:18081`. In-page `fetch` wrapper. Bindings as lengths only. R9b/R9c browser zone `America/Los_Angeles`. R8c zone forced to `Australia/Lord_Howe` via CDP after those two shots.

Seed script POSTed one review per new row before the browser. Those calls are **not** in this table.

| t (UTC) | Method | Path tail | Request | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 03:46:16 | POST | happy `4478c5a0-…/recover/review` | `disposition_id`, rev **78** | **200** ×2 | Open. StrictMode pair. `review_ok` true. No catch-up fields. |
| 03:46:28 | POST | happy `…/recover` | `disposition_id`, rev **78**, `review_binding` len recorded, `authorize_instant` | **200** | `catch_up_task_id` `5a6a42ca-5a5c-40ba-ae4d-5264915b0e15`. One POST. |
| 03:48:40 | POST | dirty `23767d68-…/recover/review` | `disposition_id`, rev **79** | **200** ×2 | Open after unsaved title + notes. `review_ok` true. |
| 03:48:48 | POST | dirty `…/recover` | `disposition_id`, rev **79**, binding, `authorize_instant` | **200** | `catch_up_task_id` `ea307cff-a3f8-453a-9054-dd092b665168`. |
| 03:50:30 | POST | c2 `02a87d26-…/recover/review` | `disposition_id`, rev **80** | **200** ×2 | `review_ok` false. Lord Howe zone already applied. |
| — | — | c2 catch-up due `2026-04-05T01:45` then Refresh | **no further POST** | — | Client fold alert. Ledger did not grow. |

Session methods: **GET** and **POST** only. API log on `:18081`: **no** `PATCH`.

### DB read-back (`theplan_s1_test`, after bounce2)

| Row | Result |
| --- | --- |
| Happy `4478c5a0-…` | `recovered`; due `2026-10-27 03:00:00+00`; catch-up `5a6a42ca-…` |
| Dirty `23767d68-…` | `recovered`; title still `REC-UI-dirty weekly`; description still `seed notes`; due `2026-10-27 03:00:00+00`; catch-up `ea307cff-…` |
| C2 / fixed / LA fold / LA gap | still `unresolved_held` |

## R9d at `da5a535` (browser, not the seed probe)

**Runner:** Renee. Vite `:5174` → API `:18081`. In-page `fetch` wrapper installed after an existing Nebula session cookie, before search. Bindings as lengths only. Browser zone `America/Los_Angeles`.

Seed script POSTed one review per new row before the browser. Those calls are **not** in this table. C2 / fixed / fold / gap were not opened in the browser.

Happy task `57cad740-2ee6-4f80-9fd2-4072647e122b`, disposition `8c8a3ffb-e9f2-47e2-8419-bdf403d2f772`.

| t (UTC) | Method | Path tail | Request | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 04:07:43 | POST | happy `57cad740-…/recover/review` | `disposition_id`, rev **85** | **200** ×2 | Open Recover. StrictMode pair. Keys only those two. |
| 04:07:58 | POST | happy `…/recover` | `disposition_id`, rev **85**, `review_binding` len **1188**, `authorize_instant` | **200** | `catch_up_task_id` `48100264-324f-4065-b915-d96a8b95edb2`. One POST. |
| — | — | Open catch-up → Unsaved → **Cancel** | **no further POST** | — | Edits and **Open catch-up task** stayed. |
| — | — | Open catch-up again → **Discard** | GET catch-up `48100264-…` | **200** | Panel title `REC-UI-happy weekly (catch-up)`. No second authorize. |

Session mutating methods after the wrapper: **POST** only (the review pair and the one authorize). API access log for the whole `:18081` process: **no** `PATCH`, **no** `PUT`, **no** `DELETE`, exactly **one** `POST …/recover`.

### DB read-back (`theplan_s1_test` @ `043`, after R9d)

| Row | Result |
| --- | --- |
| Happy `57cad740-…` | `recovered`; title still `REC-UI-happy weekly`; description still null; due `2026-10-27 04:00:00+00` |
| Catch-up `48100264-…` | title `REC-UI-happy weekly (catch-up)`; due null (no catch-up due override) |
