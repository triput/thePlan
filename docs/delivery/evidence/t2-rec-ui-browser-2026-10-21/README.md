# T2-REC-UI synthetic browser evidence (2026-10-21)

**Runner:** Renee. **Not** an independent Dex pass.

**Code:** first pass web `ab04fad` (ancestor includes API `b16493e`). **R3 re-run** after `15ef355` (authorize echoes the bound review wire). Disposable Postgres `theplan_s1_test` @ `127.0.0.1:5433`, Alembic `043_recovery_epoch`. `SEED_DEMO_USER=false`.

**Ports:** Vite `http://127.0.0.1:5174` proxies `/api` to API `http://127.0.0.1:18081`. Household/prior listeners on **`:8000` and `:5173` were already busy and were not used.** `:8080` was also busy and unused. No live Graph/Google. No push.

**Operator:** existing disposable `nebula@localhost` (credentials stay in gitignored `.secrets-backup/nebula-credentials.txt`). Browser zone `America/Los_Angeles`. Series rule zone `UTC` (completion-anchored weekly).

**Seed:** `REC-UI-happy weekly` (`7dac39ef-3bc2-4eeb-9b3e-4bf7c0938ced`, disposition `8f7a5537-756b-478c-8c5f-492235ed52b9`) and `REC-UI-c2 blocks` (`532fd950-e8d3-48c7-9d8e-2f4753a4ce83`, disposition `db7df4be-c50b-462a-a8d1-4405e6102fcb`, pinned block). Session helper `apps/api/_tmp_seed_rec_ui.py` and `apps/web/vite.synthetic-rec-ui.config.ts` are untracked and not product.

| Shot | Claim |
| --- | --- |
| `R1-review-before-authorize.png` | Open Recover on happy task. Review fields visible **before** authorize: cadence, server authorize instant, next-normal target/effort, historical work, catch-up default 60. Option A labels: `Editing in America/Los_Angeles (browser local)` and `Rule zone UTC`. Authorize enabled. |
| `R2-stale-after-edit.png` | Catch-up remaining edited 60 → 45. Copy: “Review is stale after edits — refresh before Authorize.” Authorize disabled. No authorize POST yet. |
| `R3-authorize-intent-mismatch.png` | **Pre-fix (`ab04fad`), superseded.** Refresh bound remaining 45; Authorize omitted it. **422** `REVIEW_BINDING_MISMATCH`. |
| `R3-authorize-remaining-45-200.png` | **Re-run (`15ef355`).** Same path on `REC-UI-r3 remaining`: edit 45, Refresh review, Authorize. POST included `catch_up_remaining_minutes: 45` plus binding. **200**. Held banner cleared. DB catch-up `ce1e6338-bbdb-4e00-b984-b5854a095f6a` remaining **45**; disposition `recovered`. Success pane still unmounts with the held row. |
| `R4-authorize-success-held-cleared.png` / `R4b-scheduling-no-held.png` | Fresh Recover (no remaining edit) then Authorize **200**. Held banner gone from Scheduling. Success pane “Recovered” did not stay on screen (banner unmounted with the held row). DB: disposition `recovered`; catch-up `e2cf82d9-3805-4790-9916-8ec9a4888294` title `REC-UI-happy weekly (catch-up)` remaining **60**; series due `2026-10-27 02:00:00+00:00`. |
| `R5-c2-blocks-prevent.png` | C2 review shows `Recovery blocked: BLOCKS_PREVENT_NEXT_NORMAL` and the same-task blocks/pins sentence. No delete/unpin/manual-clear control. Authorize disabled. No authorize POST. Disposition stayed `unresolved_held`. |

Request detail: `REQUEST-LEDGER.md`.

**Also observed:** each Recover open issued **two** identical `recover/review` POSTs (Vite dev). Both 200 and read-only. Closing the happy task after success raised an unsaved-changes dialog; Discard was chosen. Resource log has no task PATCH and no replan/apply/preview POST.
