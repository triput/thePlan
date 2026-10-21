# W10 observed request ledger (Dex bounce) — 2026-10-21

**Capture method:** in-page `fetch` wrapper on Vite `http://127.0.0.1:5173` (Jim Cursor browser / Dex IAB target). Mutating calls only; auth omitted. **No** Apply / Preview apply / replan / provider / sync URLs observed.

**Stack:** Vite `:5173` → API `:8000` → Postgres `theplan_s1_test` `:5433`. Nebula synthetic seed (see `SYNTHETIC-SIGNIN.md`).

## Observed mutating calls (this session)

| t (UTC) | Method | Path | Request body (exact) | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 21:41:36 | POST | `/api/v1/schedule/held-misses/60e7a045-f730-4488-b24a-b2ee9ad92ba9/leave-held` | `{"expected_revision":53}` | **200** | Leave held success; stays unresolved |
| 21:42:01 | POST | `/api/v1/schedule/held-misses/216ee3a1-e646-4a35-b722-5a29c22010bf/skip` | `{"disposition_id":"aed6679e-cd24-42be-9dec-751dfbde6b4f","expected_revision":53}` | **200** | Named `disposition_id` only |
| 21:43:01 | PATCH | `/api/v1/tasks/00f67819-9a77-481a-82fc-51613a489352` | `{"start_no_later_at":"2026-10-30T23:00:00.000Z"}` | **200** | Dates-only; **no** `title` despite dirty title in form |
| 21:43:02 | POST | `/api/v1/schedule/held-misses/00f67819-9a77-481a-82fc-51613a489352/release` | `{"disposition_id":"d0ffcf40-bf73-48af-926d-5a5cf24ddd67","expected_revision":54}` | **200** | After dates PATCH |
| 21:43:56 | POST | `/api/v1/schedule/held-misses/f9651eba-75b1-4df6-9513-a847fcc78851/leave-held` | `{"expected_revision":1}` | **409** | One-shot poisoned settings cache; **no second POST** |

## Dirty unrelated field (unsaved)

- Form title edited to `UI-held-03 DIRTY-TITLE-SHOULD-NOT-PATCH` before **Save dates & release**.
- PATCH body contained **only** `start_no_later_at` (table row above).
- After release success, title remained dirty; close prompted unsaved-changes dialog (`W10-dirty-title-after-dates-only-release.png`). Discarded after capture.

## 409 no auto-retry

- One-shot poison: next `GET /api/v1/settings` returned `scheduling_revision: 1` (live was 55).
- Leave held → single POST `expected_revision:1` → **409** `SCHEDULING_REVISION_CONFLICT` (`expected_revision:1`, `current_revision:55`).
- Alert: “Scheduling inputs changed since this action was prepared”; banner stayed held (`W10-409-no-retry.png`).
- **No** automatic second leave/skip/release POST after the 409.

## Negative scan

- `apply` / `replan` / `provider` / `sync` mutating URLs: **none** in ledger for this session.
