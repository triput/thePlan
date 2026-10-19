# T1-A — Apply busy-input trust recheck (2026-10-19)

**Status:** Local review tip `a603822` on `78f767a` (supernova); **not pushed** to `origin` as of cloud mirror check.

**Authorization:** Trish approved Dex’s narrow fix (Cabinet thread, 2026-10-19 ~4:11 PM PT): trust recheck on Apply immediately before writes, plus regression test. Microsoft `showAs` mapping remains **T1-D**. No push/deploy/live Apply/replan.

## Production change (`schedule_preview_apply.py`)

1. **`_validate_ready_for_apply`:** After `collect_inputs(..., now)`, call `require_busy_input_trust` on the collected result.
2. **Before `ScheduleRun` / `apply_calculation`:** After replay `collect_inputs`, call `require_busy_input_trust` again (post-lock path).
3. **`BusyInputTrustError`:** HTTP **409** with code **`BUSY_INPUT_TRUST`**, trust diagnostics in response extras. **Zero domain writes** on reject (no run row, no blocks, no receipt).

## Regression test

- **Name:** `test_t1a_apply_rejects_unknown_busy_input_trust_without_domain_writes`
- **Scenario:** Ready preview → in-horizon Microsoft `ExternalCalendarEvent` with null transparency/provenance → Apply → **409** / **`BUSY_INPUT_TRUST`**; assert no block or schedule-run writes.
- **Disposable DB:** `theplan_t1a_test` (isolated T1-A container, not household).
- **Evidence:** `t1a-fixtures/t1a-apply-trust-pytest.txt` — **3 passed** (new test + 2 existing apply happy paths).

## S2-V4 provenance (packet label)

S2 suite **20/20** at schema **034** was captured as commit **`61e639e`** plus the **test-only** `_REQUIRED_HEAD` pin later committed as **`78f767a`** (`test_s2_v4_assignments.py` only). Dex: no rerun required when that diff is documented (`s2-v4-034-61e639e.txt`).

## Prior validation tips (same branch, local)

| Tip | Scope |
|-----|--------|
| `61e639e` | Matrix dispositions, isolation guards, horizon fixture |
| `78f767a` | S2 assignments alembic head pin → `034_external_event_free_busy` |
| `a603822` | Apply trust recheck + regression |

## Residual (unchanged)

- Apply of **already-ready** preview when busy revision does not advance: fingerprint may not stale via revision; trust recheck on Apply closes the gap for **new** unknown in-horizon events at apply time.
- Outlook `showAs` / T1-D not in this slice.

## Integrated review (Dex)

- [ ] Both trust gates on real Apply entry path (validate + pre-apply collect).
- [ ] 409 extras usable for operator diagnostics; no writes on failure.
- [ ] Regression proves MS null transparency blocks Apply without mutating domain tables.
- [ ] Existing valid Apply paths still pass (happy-path tests in artifact).
