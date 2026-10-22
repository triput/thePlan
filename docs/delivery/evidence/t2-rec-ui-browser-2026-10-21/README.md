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

## Bounce re-run (Renee) — HEAD `56dde72`

**Not** an independent Dex pass. **Not** acceptance of tip `bf5b298`. Prior R1–R5 above stay attributed to `ab04fad` / `15ef355`. This pass is the post-bounce web (`56dde72`) on API `ce4dc08`, same ports: Vite `http://127.0.0.1:5174` → API `http://127.0.0.1:18081` → Postgres `theplan_s1_test` `:5433`. **Not** `:8000`. Browser zone `America/Los_Angeles` (`Intl`). No push.

| Shot | Claim | Result |
| --- | --- | --- |
| `R6-zone-labels-la-vs-utc.png` | Happy series rule zone UTC ≠ browser LA | **GREEN** — copy: `Editing in America/Los_Angeles (browser local) · targets above use Rule zone UTC` |
| (ledger, no separate shot) | Two refreshes keep due + deadline + remaining; edit remaining only keeps the dates | **GREEN** — review bodies below |
| `R7-ooo-review-discarded.png` | Late review 200 discarded when generation moved | **GREEN** on the second hold (see honesty). Remaining stayed **88**; Authorize stayed disabled; review time did not advance |
| `R8-la-fold-client-reject.png` | Catch-up due `2026-11-01T01:30` (LA fold) rejected in the editor | **GREEN** — diagnostic shown; **no** `recover/review` POST |
| `R8b-la-gap-client-reject.png` | Catch-up due `2026-03-08T02:30` (LA gap) same fail-closed | **GREEN** — same diagnostic; **no** review POST |
| `R9-durable-catchup-cta.png` | After authorize 200, catch-up link stays on Scheduling once the held row is gone | **GREEN** — `Create catch-up` visible; held banner gone. Click opened `REC-UI-happy weekly (catch-up)` after Discard on the unsaved-series dialog |
| `R10-fixed-past-choice.png` | Fixed series whose one-step landing is still past | **GREEN** — `FIXED_PAST_REQUIRES_CHOICE`; Authorize disabled; no authorize POST |
| `R11-la-fold-server-422.png` | Rule-zone LA daily whose next wall is the fall fold | **GREEN** — browser `recover/review` **422** `BOUNDS_ROLL_INDETERMINATE_LOCAL` `kind=fold` `field=due_at` |
| `R11b-la-gap-server-422.png` | Rule-zone LA daily whose next wall is the spring gap | **GREEN** — browser `recover/review` **422** `kind=gap` |

**Honesty (this pass):**

- Client fold/gap is local validation. Refresh showed “Reviewing…” while settings loaded, then the alert, and the in-page ledger did **not** gain a review POST. Server fold/gap are separate seeded tasks and **did** POST.
- Out-of-order: a first 3500ms hold (remaining 50) **was applied** — the edit landed after the hold expired. The counted discard is the later 1200ms hold: real POST **200** with remaining **77**, response withheld in-page, remaining edited to **88** before the response was delivered. Review time stayed `03:20` UTC. Authorize stayed disabled.
- That edit was a DOM `input` event on the remaining field while the real response was held, not a unit-test mock of `shouldApplyReviewResponse`.
- Vite StrictMode still doubled the open `recover/review` (happy, fixed, fold, gap). Explicit refreshes were single.
- Opening the catch-up from the CTA raised **Unsaved task changes** because the series draft still showed the pre-advance dates. **Discard** was chosen. API log on `:18081` has **no** `PATCH` in this session.
- C2 was not re-clicked. `REC-UI-c2 blocks` stayed `unresolved_held`.
- DB read-back on `theplan_s1_test`: happy disposition `recovered`, series due `2026-10-27 03:00:00+00`, catch-up `9566f9a5-812a-4c3b-81b2-dc5c51a1fbd9` due `2026-10-28 22:30:00+00` remaining **45**. Fixed, fold, and gap dispositions stayed `unresolved_held`.

## Bounce2 re-run (Renee) — HEAD `2b290eb`

**Not** an independent Dex pass. **Not** a Dex tip. Prior R1–R5 stay on `ab04fad` / `15ef355`. Prior R6–R11b stay on web `56dde72` / API `ce4dc08` (tip paper `24b1e4b`). Those rows were **not** re-clicked at this pin.

**This pass:** API `2b290eb` (parent web `ebff398`). Vite `http://127.0.0.1:5174` → API `http://127.0.0.1:18081` → Postgres `theplan_s1_test` `:5433`, Alembic `043_recovery_epoch`. `SEED_DEMO_USER=false`. **Not** `:8000`. No push. No household migrate.

**Tests at this pin (not the browser):**

- `apps/api` `test_s2_t2_rec_ui_binding.py` + `test_s2_t2_rec_recovery.py`: **54 passed** (15 binding, including `test_a_bind_idempotent_rejects_alternate_valid_review_after_commit`; 39 recovery) in 35.67s. Disposable DSN `postgresql+psycopg://t1a@127.0.0.1:5433/theplan_s1_test`.
- `apps/web` `npm test` is **node:test**, not a vitest binary: **94 passed**, 0 failed.
- `apps/web` `npm run build` (`tsc -b && vite build`): **exit 0**.

| Shot | Claim | Result |
| --- | --- | --- |
| `R9b-clean-open-catchup.png` | Clean series draft, authorize, then **Open catch-up task** with no Unsaved Discard and no task PATCH | **GREEN** |
| `R9c-dirty-title-notes-protected.png` | Dirty title + notes still block the catch-up switch; server title/notes not written | **GREEN** |
| `R8c-lord-howe-fold-client-reject.png` | Lord Howe 30min fall fold rejected in the catch-up editor | **GREEN** for the fold. Spring gap was **not** re-clicked here; the node suite covers it |

**R9b (browser zone `America/Los_Angeles`).** Task `REC-UI-happy weekly` `4478c5a0-a85e-45d4-ada6-461ef7d4b05d`. Open review **200** ×2 (StrictMode), rev **78**, no catch-up fields. Authorize **200** once, rev 78, `catch_up_task_id` `5a6a42ca-5a5c-40ba-ae4d-5264915b0e15`. Due field moved `2026-10-18T20:00` → `2026-10-26T20:00` (LA) before the click. Title stayed `REC-UI-happy weekly`. **Open catch-up task** opened `REC-UI-happy weekly (catch-up)` with **no** dialog. In-page ledger methods for the whole session: **GET and POST only**.

**R9c (same LA zone, second held series).** `REC-UI-dirty weekly` `23767d68-89a8-4f35-82c9-89f4d29e2a46`. Title set to `REC-UI-dirty weekly operator edit`, description to `bounce2 notes stay dirty`, not saved. Review **200** ×2 rev **79**. Authorize **200**, `catch_up_task_id` `ea307cff-a3f8-453a-9054-dd092b665168`. After authorize the due/deadline/bounds showed the rolled series and the title and notes were still the edits. **Open catch-up task** raised **Unsaved task changes** / “Save your edits before opening the other task?” (Cancel, Discard, Save and open). **Cancel** was chosen. Title and notes stayed in the form. No PATCH.

**R8c.** CDP `Emulation.setTimezoneOverride` set the page zone to `Australia/Lord_Howe` (`Intl` read-back matched). On still-held `REC-UI-c2 blocks`, catch-up due `2026-04-05T01:45` then Refresh. Alert: “Catch-up due is not a valid wall clock in browser local (gap/fold) — pick an unambiguous time.” Editor copy: `Editing in Australia/Lord_Howe (browser local)`. No review POST after that refresh (last C2 reviews are the open pair at 03:50:30Z, keys only `disposition_id` + `expected_revision` 80, `review_ok` false). Held-banner instants on that pane still say `America/Los_Angeles` (settings zone). The override was cleared after the shot.

**Honesty (this pass):**

- R6–R11b are **not** re-verified at `2b290eb`.
- R9c Cancel does **not** bring **Open catch-up task** back. The button clears the success id before the dirty guard runs. The edits stayed; the CTA did not. Catch-up row was already in the inbox.
- After the R9c shot, Discard was used only to leave that series for the Lord Howe probe. DB description on the dirty series is still `seed notes`, title still `REC-UI-dirty weekly` (the operator edit was never saved).
- A mis-click opened the subtask composer on `REC-UI-la gap` and was cancelled. No subtask was created.
- DB read-back (`theplan_s1_test` @ `043`): happy and dirty series `recovered`, both due `2026-10-27 03:00:00+00`. Catch-ups `5a6a42ca-…` and `ea307cff-…` exist. C2, fixed, LA fold, and LA gap stayed `unresolved_held`. API access log on `:18081`: **no** `PATCH`.
