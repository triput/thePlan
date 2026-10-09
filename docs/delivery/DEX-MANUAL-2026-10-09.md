# Dex manual checklist evidence

**Filename:** DEX-MANUAL-2026-10-09.md

**Last modified:** 2026-10-09

**Version:** 1.0

**Tested build:** frozen `cc87349` (includes `93dbbcb` and keyboard fix `0c36ee2`).

## Scope

Second-eyes operator pass against a disposable local Compose stack at localhost:18080. Synthetic account, tasks, pins, archived containers, dependencies, and a second owner. No household data or calendar integrations. Database revision `023_schedule_outcome_provenance`; production web build passed. Active F4 checkout changes were excluded by testing a Git archive.

The canonical [MANUAL-CHECKLIST.md](./MANUAL-CHECKLIST.md) records Dex coverage beneath each row. Checked boxes mean the stated local check has evidence, not Trish's final sign-off. Some evidence is CLI or direct HTTP, explicitly labeled. Earlier browser evidence on `0199edf` is identified where reused; it is not presented as a fresh retest.

## Confirmed defect: archived lifecycle must precede style exclusion (P2)

Reproduction:

1. Create an archived project with `schedule_style=manual` and an open task inheriting that style.
2. Also create an archived epic with a child project using `bundle`, and an open task in that project.
3. Run Update Schedule.
4. Read the task explanations through CLI/API; use global task search to open the archived manual task's web detail.

Expected: `excluded_lifecycle_archived`, as required by the checklist, with lifecycle taking precedence over style.

Actual: both tasks report `excluded_manual_or_bundle`. Web copy for the first is “Excluded from auto-scheduling (manual via project).” The other says bundle via project.

Cause: `load_excluded_tasks` in `apps/api/app/scheduler/candidates.py` classifies style/pin exclusions without skipping archived scopes. Collect adds those IDs to `already_evaluated`, so `load_lifecycle_excluded_tasks` skips them. Apply lifecycle classification first, or exclude lifecycle-ineligible tasks from style/pin classification. Check fully pinned archived tasks alongside manual/bundle cases.

Run: `d71f46a7-b953-4fe8-a953-391b72ce420c`. This defect was found by the extended checklist pass after the earlier focused code-review hold was lifted.

**Working tree (not on frozen build):** Addressed in `load_excluded_tasks` (`apps/api/app/scheduler/candidates.py`) — archived lifecycle classification now precedes manual/bundle/full-pin. Automated regression: `test_archived_lifecycle_precedes_style_and_full_pins` and related cases (**4 passed**). Fail record above stays accurate for **`cc87349`**; Dex/operator retest pending.

## Passed in this pass

- CLI login with a separate test session file; hierarchy create/get/list/patch for epic, project and section.
- Handoff proposal JSON with embedded 30-minute/P4 defaults and matching text tree; fresh-key apply, receipt equality and replay. Task-only graft into existing section preserves standalone host project while new tasks are manual. Web Advanced section shows `dex-checklist / QA-F1` source reference.
- Dependency CLI add/list/remove; workflow waiting transition and filtered board-order list. Actual browser-moved task readback: `workflow_state=waiting`, `board_column=waiting`, `board_revision=2`, note `Drag verification`.
- Identical outline imported through the UI twice; two same-title epics appeared, confirming intentional duplication.
- Work epic filter narrows to the six Edge Cases tasks. Prior project-filter and owner-wide checks also have evidence. Archived project itself absent from picker; see caveat below for projects under archived epics.
- Recurring task stays Ready, due advances, and toast “Recurring task advanced to next occurrence” was directly observed.
- Completed task uncompleted into In progress; list showed unchecked “Mark ... complete.”
- Today and Upcoming include pinned, scheduled tasks with null due dates after explicit All/All filter reset.
- Independent session completed the browser's Ready task. Old-revision request returned HTTP 409 with `BOARD_REVISION_CONFLICT`, expected 0/current 1. Stale browser move refreshed the card into Done rather than overwriting completion.
- Cross-column drag from In progress into empty Waiting opened its note prompt; save preserved note and Schedulable badge.
- Pinned estimate coverage: explanation correct; direct API block inspection found one pinned block and no new unpinned block for the task.
- Partial horizon case placed 1320/3000 minutes; remaining 1680 generated `unplaced_horizon_exhausted` plus minimum-block fact. Browser displayed both lines.
- Binding deadline generated `unplaced_deadline_limit`; browser displayed deadline and remaining minutes.
- Current-build estimate edit 30 -> 45: reopening retained the old 30-minute result and same run ID, showed Stale, and tooltip read `Inputs changed since last run: duration changed`. No replan was started by the edit.
- Cycle A/B each named only A/B; downstream named `blocked_prerequisite`. CLI/API evidence, not a browser check of all three panels.
- Completed/trash lifecycle exclusions correct. Archived style precedence failed as above.
- CLI `human_summary` matched `summary_text`; placed explanation included `algorithm_version=f3-w2` and nonempty `placement_facts`.
- CLI runs list/get and explanations offsets 0 and 2 (limit 2) matched direct API responses. A second owner received 404 for foreign run, run explanations, and task explanation.
- Default API task list excluded both archived project and archived-epic tasks; explicit archived project task query included its task.

## Partial / user follow-up

- **Keyboard:** Space/Enter no longer opened task details. ArrowDown/Enter moved the task to In progress. Native popup opening itself was not observable reliably; retain that narrow human check.
- **Drag:** empty-column Waiting move passed. Attempts to target peers for precise insertion and a parent drop into Done did not complete reliably through the browser control. Do not call these either pass or confirmed defect. Parent/child policy via menu passed in the earlier smoke.
- **Archived navigation:** Archived view provides Restore buttons but no project-open control. Clicking project title did nothing. API explicit-project inclusion passed; browser archived project detail remains unverified.
- **Archived picker:** the archived project and archived epic themselves are omitted, but an active project under the archived epic remains in All-projects options (`QA Under Archived Epic`). Clarify whether the picker must hide descendants too; default unfiltered task listing correctly hides their tasks.
- **Saved-filter observation:** the previous disposable database's selected project ID survived in browser storage. With that ID absent from the new database, the dropdown appeared All projects while results were empty. Explicitly selecting All fixed it. This was a test-database replacement scenario; do not infer a normal archive/delete reproduction without testing it.
- Household setup and sign-in as Trish were intentionally not exercised. These remain her checks.

## Earlier evidence retained

Browser smoke on `0199edf`: 52 Ready/32 Done load-more and move-reset repopulation; WIP and Waiting scheduling independence; roots-only; parent completion cancel/bulk; never-evaluated panel; mixed manual/bundle run; blocker completion -> placed; duration edit -> Stale -> replan refresh. Lifecycle stale tooltip also verified. Backend corrections were subsequently reviewed and 16 focused regressions passed at `93dbbcb`; those automated checks are not browser evidence.

## Reproduction artifacts

Local scratch directory:

`C:\Users\trish\.codex\visualizations\2026\10\08\01a11d56-e98c-7c31-995d-8b17c9a41e5a\checklist-smoke`

Contains frozen source, Compose config, synthetic fixture scripts, CLI evidence JSON, explanation evidence JSON, supplementary API observations, and `archived-reason-failure.png`. Fixture harness corrections (Path serialization, response envelope and pagination argument) were test-driver errors, not product defects. The duplicate CLI hierarchy names came from rerunning fixture setup after a driver error.

No production data changed and no source fixes or pushes performed. Checklist/evidence documentation are the only intended repository edits from this pass. Temporary test containers are removed after evidence capture; scratch artifacts are retained.
