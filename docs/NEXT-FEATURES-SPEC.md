# thePlan next feature implementation specification

**File:** `docs/NEXT-FEATURES-SPEC.md`  
**Version:** 1.0  
**Last modified:** 2026-10-08  
**Product owner:** Trish  
**Audience:** Implementation and QA team  
**Status:** Handoff specification. All seven features are in scope; no implementation is claimed by this document.

## 1 Purpose and delivery agreement

Make thePlan easier to populate from an agreed planning conversation, easier to use for visual work management, and easier to understand when it schedules work. Preserve the personal, local-first product and its existing task hierarchy. The user should not have to re-enter decisions merely to put them into the right application fields.

Trish has explicitly selected all seven features, in this order:

| Slice | Capability | User outcome |
|---|---|---|
| F1 | CLI planning handoff | Put an agreed project structure into thePlan and receive a reliable receipt |
| F2 | Kanban for work in progress | See and change the progress of existing tasks on a board |
| F3 | Scheduler explanations | Understand why work was placed, excluded, or left without enough time |
| F4 | Temporary Time Map overrides | Change availability for specified dates without repairing normal settings later |
| F5 | Small Coursera template set | Start a specialization, course, or module with less structural paperwork |
| F6 | Replan preview | Inspect the schedule changes before choosing to apply them |
| F7 | Saved views | Reuse named filters in the web UI and CLI |

Implementation and automated verification proceed by slice. Manual verification may trail implementation; this is an explicit delivery choice, not a reason to stop the next slice. Maintain visible evidence and a runnable manual checklist. Investigate a concrete uncertain dependency before building on it. Do not make a blanket manual sign-off gate between slices.

The feature scope and order above are user decisions. Details explicitly called **design defaults** below are proposed decisions supplied by this spec so implementation can proceed coherently. They are not claims that Trish personally selected every field or interaction. Raise material departures, destructive behavior changes, or a demonstrated conflict with her workflow; resolve routine engineering choices within these contracts.

## 2 Existing system and integration boundaries

Use the current implementation as the baseline, and preserve these existing capabilities:

- FastAPI and PostgreSQL own domain rules. React and the CLI consume the same authenticated, owner-scoped API.
- Epic → Project → Section → Task → subtask → nested subtask remains the hierarchy. Sections and task nesting are different concepts; maximum task nesting remains two levels below a root task.
- The CLI already provides authentication, status, task list/get/create/patch, and Assist propose/apply. JSON is its default output; `--format text` serves terminal users. Preserve the current exit-code contract.
- Outline import already provides deterministic propose/apply, `coursera_specialization`, `hierarchy_v1`, and attachment under existing epics, projects, or sections. Current outline re-import is not idempotent. Its actions do not yet represent the complete F1 contract.
- `ScheduleStatus` describes scheduling and completion; `schedule_style` controls scheduling eligibility. Neither is a Kanban workflow column.
- `SavedFilter` already exists with owner, name, slug, `predicate_json`, system flag, and sort order. Extend it rather than inventing another task store.
- Replanning is explicit and dispatched to the Compose scheduler. Keep ordinary task CRUD responsive. Proposals and previews must never call calendar-provider write operations.

Reference documents: [architecture](09-technical-architecture.md), [API contract](05-api-contract.md), [CLI](CLI.md), [outline ingest](OUTLINE-INGEST.md), [scheduling ADR](adr/ADR-006-fuzzy-scheduling.md), and [calendar bundles ADR](adr/ADR-012-calendar-bundles.md).

### Closeout work and deferred scope

Two review follow-ups were sent back to the coding team: prerequisite enforcement for tasks omitted from automatic-placement candidates, and flushing repaired parent relationships before purging. Verify their status at implementation start. Their closure is required before claiming the dependent scheduling or trash behavior verified; independent feature work may continue.

Failed remote mirror deletion and durable retry handling are explicitly deferred to a future release. Carry that known limitation in scheduling and preview receipts; do not silently treat calendar-provider success as part of a local database commit.

Desktop packaging remains parked. This work does not include LiveBytes distribution, a general template marketplace, Coursera login/scraping/progress synchronization, autonomous replanning, team workspaces, or automatic Squirrel Board updates.

## 3 Shared contracts

### Ownership and explicit intent

Every resource, reference, receipt, explanation, preview, and saved view is scoped to the authenticated owner. Validate existing parent IDs and task references on apply, not just during proposal. The CLI uses normal session authentication; it gets no recovery-command shortcut into domain data.

An agreed plan can be applied on the user's instruction without an additional mandatory GUI approval ceremony. Separate propose and apply commands make the operation reviewable; an explicit apply command is the write boundary. Conversational brainstorming does not itself authorize an apply. Store optional source references without calling the source service or modifying its state.

### Defaults and omissions

Distinguish omitted fields from explicit values and explicit nulls. Do not invent due dates, deadlines, dependencies, or priority claims. Where current persistence requires a priority or duration, resolve the existing product default and include that fact in the proposal and receipt. Never describe a default estimate as a user-supplied estimate.

**Design default:** New bulk planning handoffs and template instances use a manual/backlog scheduling policy unless the submitted proposal explicitly selects inherited or automatic scheduling. Apply that policy to the created root when inheritance can express it, and to new tasks when attaching below an existing root. Do not change the destination parent's scheduling policy or siblings. Existing quick-add and task-create defaults remain unchanged. This limits accidental scheduling floods without adding a new activation system.

### Consistent writes and concurrent edits

New bulk operations must validate the full graph before writing and commit the approved graph atomically. A failed apply must not leave a half-created project. Preserve existing public outline behavior until it is deliberately migrated; do not silently change legacy response or partial-failure contracts.

Use database-enforced idempotency for new bulk applies. Keys are scoped by owner and operation kind. Same key plus same canonical payload returns the original result without creating anything; same key plus different payload returns a conflict. Concurrent identical submissions must create only one graph. Persist the receipt in the same transaction as the created graph. A response lost after commit is recoverable by key. Retain receipts for this release; deleting created entities must not allow replay to recreate them.

Receipts include operation ID, source references, entity keys and IDs, navigable links where supported, created/defaulted/skipped counts, warnings, and any explicitly deferred external effects. Claimed agent names are optional descriptive metadata, never authentication identities.

### Shared scheduling calculation

Prepare for F6 while implementing F3: separate scheduling input collection, calculation, and application. One calculation produces proposed blocks, task outcomes, and structured reason facts. Direct replan applies that result; preview stores it without applying. Do not build a second preview scheduler or generate explanations by asking a language model to guess from the final calendar.

Scheduling inputs include effective inherited rules, dependency state including non-candidate prerequisites, pinned blocks, relevant external busy data, durations, priorities, settings, and overrides. Evaluation time and timezone are explicit inputs. Equal inputs and evaluation time must produce stable results, including deterministic tie-breaking.

## 4 F1 CLI planning handoff

### User workflow

After discussing an idea, the operator or assistant prepares a versioned JSON graph. The CLI validates and proposes it, showing the structure, resolved defaults, target location, and scheduling policy. On explicit apply it creates the graph and returns a receipt. A source idea ID and URL can travel with the project so its purpose survives the handoff.

### Required capabilities

- Add list/get/create/patch commands for epics, projects, and sections; add task complete/uncomplete and dependency list/add/remove commands using existing API semantics. Do not introduce new destructive delete commands as an incidental part of this slice.
- Add a bulk `handoff` command family: propose, apply, and receipt lookup. Avoid naming it `plans`, because thePlan already has a distinct Plan entity for scheduling targets.
- Accept a UTF-8 file or stdin; JSON output remains the scripting contract. Human text output summarizes the tree and defaults without exposing private unrelated data.
- Support a new epic tree, a standalone project, or additions beneath an owned existing epic/project/section. Do not fabricate an epic just to satisfy the older outline mapper.
- Support task nesting, descriptions, labels, estimates, explicit priority/date fields, schedule policy, and dependencies between new tasks or owned existing tasks. Omitted dependencies remain absent. Validate hierarchy depth and dependency cycles before apply.
- Preserve task titles and explanatory wording. No LLM or external access is required to ingest an already agreed structure.
- Reuse or extract existing outline mapping and apply services where appropriate. Implement the missing graph and transaction semantics in the API, not a shell loop of independent POST requests.

### Proposed command and payload shape

These command names and fields are design defaults for implementation, not existing commands:

```text
theplan handoff propose --file project.json
theplan handoff apply --file approved-project.json --idempotency-key <uuid>
theplan handoff receipt --idempotency-key <uuid>
```

```json
{
  "schema_version": 1,
  "source_refs": [{"system": "squirrel-board", "id": "IDEA-example", "url": "https://example.invalid/ideas/example"}],
  "schedule_policy": "manual",
  "entities": [
    {"key": "project", "kind": "project", "title": "Build the agreed experiment", "description": "Purpose and decisions from the planning conversation."},
    {"key": "section", "kind": "section", "parent_key": "project", "title": "First working slice"},
    {"key": "design", "kind": "task", "parent_key": "section", "title": "Describe the acceptance examples"},
    {"key": "build", "kind": "task", "parent_key": "section", "title": "Implement the first slice"}
  ],
  "dependencies": [{"blocking_key": "design", "dependent_key": "build"}]
}
```

Allow explicit existing-parent references using `{kind, id}` in place of `parent_key`, never both. Local keys must be unique. Normalize the graph into a stable action order; report validation errors with entity key and field. The proposal must return the canonical apply payload plus resolved defaults and warnings. Revalidate it on apply; edited proposals are permitted, but are not trusted server state.

Store source references in structured metadata on the receipt and created root entity. Display them in project/epic detail; a task-only graft retains its source on the receipt and new tasks. Do not parse source identity back out of free-form descriptions. Source links are ordinary links, not instructions to fetch or execute.

### Acceptance evidence

- F1-A: A graph creates a project, two sections, nested tasks, and dependencies; all relationships and source references survive readback.
- F1-B: Applying the same key twice, including concurrent calls and a simulated lost response, yields one graph and one stable receipt.
- F1-C: An invalid/foreign parent, cycle, or invalid task causes no partial writes. A changed payload with a reused key conflicts.
- F1-D: A task-only graft does not change existing parent policy. New manual tasks stay out of replan; explicit inherited policy is honored.
- F1-E: Omitted dates stay absent; mandatory duration/priority defaults are disclosed. Ordinary single-task CLI behavior remains compatible.

**Delivery (post–Quality exit):** [delivery/F1-HANDOFF.md](./delivery/F1-HANDOFF.md). **Outline ingest** ([OUTLINE-INGEST.md](./OUTLINE-INGEST.md)) is a different entry path; outline re-import remains non-idempotent — use F1 handoff + idempotency key for agreed-plan bulk create with receipt replay.

## 5 F2 Kanban for work in progress

### Board behavior

Provide List/Board selection for a project and an owner-wide Work board with project/epic filters. Both show the existing tasks. Remember the operator's selected presentation without duplicating tasks or changing their hierarchy.

**Design default columns:** Ready, In progress, Waiting, Done. Waiting has an optional short note, such as a response or resource being awaited. Start with fixed columns; custom workflows, mandatory WIP limits, and analytics are outside this slice. Show truthful per-column counts and a WIP summary for In progress and Waiting. Counts represent tasks, not estimated throughput or productivity scores.

Add an independent task workflow field for open states: `ready`, `in_progress`, `waiting`. Derive Done from existing completion state. A scheduled task can still be Ready; an unscheduled task can be In progress. Existing incomplete tasks migrate to Ready, while completed tasks display Done. Do not reinterpret `ScheduleStatus` or reuse sections as columns.

Keep a separate board ordering value so dragging cards does not rewrite list/outline ordering. Use one task-level board rank for this release; filtered boards show the corresponding subsequence. Stable tie-breaking is required. Reordering within a column changes rank only; moving columns changes workflow plus rank, not dates, priority, project, section, or scheduling style.

Cards show title, project context where needed, ancestor breadcrumb for subtasks, priority, due/deadline distinctions, and relevant scheduling badges. Display each task once. Provide an explicit roots-only filter; the default includes subtasks with visible parent context. Archived projects/epics and trashed tasks are excluded by default. Done is available with bounded pagination rather than loading all historical completions.

### Completion and scheduling interactions

- Dropping in Done invokes the existing completion policy. If open children need a decision, present the same parent-only/bulk choice. Cancellation leaves the card unchanged.
- Recurring-task completion that advances the same task resets its open workflow to Ready and keeps it out of Done. Explain that it advanced to the next occurrence.
- Moving a non-recurring completed task into an open column invokes uncomplete, then sets the selected workflow atomically. Completion from list or CLI produces the same board result.
- **Design default:** Waiting is a visual workflow state only. It does not silently disable scheduling. Display whether it is still schedulable and offer the existing Manual/backlog control. Resource timing belongs in Time Maps; dependency blocking belongs in dependencies.
- Support an accessible Move to column menu, keyboard use, and mobile controls. Dragging is an optional convenience, not the only route.
- Roll back optimistic moves on failure. Use an expected workflow/rank revision to reject conflicting edits instead of silently overwriting another session's move.

### Acceptance evidence

- F2-A: Board/list/CLI show one consistent task after moves, complete/uncomplete, recurrence rollover, and edits in another session.
- F2-B: Moving a card preserves scheduling fields and hierarchy. Waiting alone does not change eligibility.
- F2-C: Open-child completion policy and cancellation work from Done; nested tasks appear once with parent context.
- F2-D: Keyboard, touch, filtered reorder, pagination, empty/error states, and failed optimistic moves are exercised. Column totals include all matching tasks, not only the loaded page.

## 6 F3 Scheduler explanations

Expose explanations in task scheduling detail and in a schedule-run summary. Add CLI access such as `schedule explain --task-id ...` and run get/list. This slice explains recorded computations; a read does not trigger a new replan.

Each result records run ID, calculation time, effective timezone/horizon, effective rule values and their inheritance sources, requested/placed/remaining minutes, and structured reason codes with factual parameters. A completed scheduling run can contain unplaced tasks. Keep calculation failure separate from inability to fit work.

Required reason families: manual/bundle exclusion, already completed/trashed/archived where applicable, duration already covered by pins, unfinished prerequisite, dependency cycle, no allowed Time Map interval, red exclusion, busy/pinned conflict, deadline limit, insufficient contiguous minimum block, project daily cap, and horizon capacity exhausted. Record reasons during evaluation. Where several constraints matter, show the observed constraints without claiming to have proved a unique root cause.

For successful placement, show when it was placed, map tier, inherited map source, applicable override, and prerequisite boundary. Explain disclosed defaults. Do not claim an exact counterfactual, such as “change this and it will fit,” unless recalculated.

Distinguish **last-run explanation** from current settings. If relevant inputs have changed, mark the explanation stale and name the change category where available. If the task has never been evaluated, say so. No fabricated explanation from an empty history. Store rule/input versions so explanations remain intelligible after subsequent edits.

Acceptance: F3-A covers each reason family and representative combinations; F3-B verifies inherited rules and pinned prerequisites; F3-C verifies stale/no-history states and owner isolation; F3-D asserts the human text and JSON derive from the same reason facts as the actual placement result.

## 7 F4 Temporary Time Map overrides

Allow an operator to replace a particular Time Map's bands and strictness for specified local calendar dates. The normal weekly map remains intact. Show overrides in map settings and the calendar overlay, including their dates, timezone, and effective intervals.

**Design defaults:** One override record contains a map ID, inclusive local start/end dates, a stored IANA timezone, replacement bands, and an explicit strict-mode value. Empty bands with strict mode mean unavailable all day. Reject overlapping override date ranges for the same map rather than introducing precedence rules. Different maps may have overlapping overrides independently.

Outside the range, use the normal map automatically; no background job must run to restore it. Keep expired entries visible in history until manually deleted. A later user-timezone change must not silently reinterpret saved override dates. Derive each local date boundary using the override's timezone, then convert to UTC; test daylight-saving transitions. For this release, reject a band crossing midnight and ask for two dated bands.

Resolve the task's inherited map first, then select that map's override for each applicable date. Red subtracts from green, yellow, and neutral availability **within that effective map only**. An override for map A never constrains map B. An unbound task has no map override. Overrides remain inside existing workday/workweek capacity rules and never move pins or external busy events; disclose this in the editor. An override may remove an earlier map restriction during its dates but does not create extra global working hours.

Creating/editing an override does not replan automatically. Show that the existing schedule may now be out of date; F3 includes effective override provenance and F6 treats changes as preview-invalidating inputs.

Acceptance: F4-A covers one-day/multi-day expiry and unchanged base maps; F4-B covers inheritance and cross-map independence; F4-C covers DST, stored timezone, and overlap validation; F4-D covers all-day unavailability, non-working days, red precedence, pins, and stale schedule indicators.

## 8 F5 Coursera templates

Deliver three useful built-in templates, extending the current deterministic importer:

| Template | Creates | Target and inputs |
|---|---|---|
| Specialization or certificate | Epic with course projects, module sections, and supplied tasks | Existing curriculum shape; optional attachment to an existing epic |
| Individual course | One project with module sections and supplied tasks | Standalone or beneath an existing epic; title, optional URL, modules |
| Course module | One section with supplied tasks | Existing project; module title and task list |

A weekly study routine is a possible later template, not a fourth required template in this release. The chosen three follow the existing hierarchy and support partial curricula without inventing a course catalog.

Provide a small template picker in the web UI plus CLI list/get/propose/apply access. Let users download example JSON and use a modest form for common fields; raw JSON editing remains available. A blank scaffold is valid and visibly distinct from an imported syllabus. Do not invent real course contents, completion records, grades, or authoritative duration estimates.

Preserve supplied titles, URLs, ordering, task-type labels, and optional-item flags. Include optional items by default with a preview toggle to exclude them. Templates are versioned; each instance records template ID/version and optional source reference. Updating a template never rewrites existing projects.

Use F1 validation, manual scheduling defaults, transactional creation, and receipts. Instance retry with the same key is safe. A new key deliberately creates a new instance, even with identical content. Semantic deduplication and merging a changed syllabus into an existing project remain deferred; warn when the supplied source is already present without pretending this is a reliable merge feature. Preserve existing importer compatibility.

Acceptance: F5-A instantiates all three shapes and attachment modes; F5-B covers optional items, empty scaffolds, supplied text/URLs, labels, and estimate disclosure; F5-C covers safe retries and deliberate second instances; F5-D verifies the existing large Coursera fixture and legacy outline contract still work.

## 9 F6 Replan preview

### Preview and apply workflow

Retain direct Update Schedule. Add Preview changes, producing an asynchronous, owner-scoped result with the same scheduling calculation used by direct replan. The result shows before/after blocks, moved/added/removed counts, affected tasks, newly unplaced or recovered work, and F3 reasons. Pins remain unchanged. Allow inspecting a task's before/after times without requiring the operator to decode raw IDs.

Preview creates only preview/run metadata. It never changes live blocks, task scheduling status, mirrors, or calendar providers. Cancellation or expiry discards the proposal. **Design default:** Apply accepts the whole proposal; selective per-block acceptance and multi-scenario comparison are deferred.

Compare normalized task/time/duration/bundle identities, not newly generated row IDs, when counting changes. A recalculation that leaves an interval unchanged must not be reported as movement merely because an internal ID differs.

### Consistency contract

Store a proposal ID, algorithm version, evaluation time, immutable proposed output, and a version/fingerprint of all scheduling-relevant inputs. The worker uses a consistent input snapshot. If those inputs change while calculation is running, mark the result stale rather than presenting it as current.

Apply must atomically validate the snapshot and replace the applicable local schedule exactly once. Use a per-owner scheduling revision and serialization scheme, or an equivalent documented transaction design, that includes all relevant writers. A check followed by an unguarded commit is insufficient. Cover task scheduling fields and lifecycle, dependencies, inherited project/epic rules, user settings, Time Maps/overrides, blocks, and external busy sync. Irrelevant text or Kanban-only changes need not invalidate a proposal.

If inputs changed, return `409 PREVIEW_STALE` with a useful change category and an action to generate a fresh preview. Never silently recalculate and apply a different schedule. **Design default:** previews expire after 15 minutes, and apply also rejects a proposal if any new block would already start in the past. Time itself can invalidate a preview even without another database write. Do not slide proposed times silently.

Apply is idempotent and returns the original receipt on retry. Concurrent direct replans and preview applies must serialize per owner. Read-only previews may be computed independently but become stale after another schedule write. Keep preview job status separate from the one-running-replan constraint introduced in migration 018.

After the local commit, mirror effects must follow the ordinary apply path and be reported separately. A provider failure must not cause replay of the local apply. Preserve the explicitly deferred mirror-retry limitation; preview does not promise distributed atomicity with external calendars.

Expose preview/get/apply through the CLI as well as the web UI. A natural-language request such as “show me what Thursday looks like if I am away” does not authorize changing live availability: this slice previews the persisted inputs only. Unsaved hypothetical overrides are a later extension.

Acceptance: F6-A proves zero domain/provider writes during preview; F6-B proves equal inputs give direct/preview calculation parity; F6-C exercises stale inputs, edits during calculation/apply, expiry, and clock passage; F6-D covers duplicate apply, competing replans, ownership, and provider failure; F6-E verifies meaningful diff counts and readable before/after display.

## 10 F7 Saved views

Add a filter builder and Save view action to task lists and boards, with a named sidebar entry. Extend `SavedFilter`; preserve system smart views. A saved view is a live query and presentation preference, not a snapshot or collection of copied task IDs.

Support project/epic, labels, priority, open workflow state, completion, schedule status/style, and due-date range. Support Inbox explicitly and distinguish “no due date” from an unbounded range. Store a versioned, validated predicate tree: AND across dimensions, OR among selected values within a dimension; labels have an explicit any/all choice. A free-form query language is out of scope.

Provide rolling date choices such as today, next seven days, and this calendar week, evaluated at query time in the user's timezone. Fixed date ranges remain fixed. Upcoming ranges use documented half-open boundaries. Persist sort and List/Board preference; workflow and scheduling status remain separate filters. Archived and trashed tasks remain excluded unless a supported explicit filter requests them; do not broaden task visibility through a saved predicate.

Allow rename, edit, reorder, and delete of user views. Deleting a view never deletes tasks. Deleting a referenced project/label must make the affected view visibly invalid or empty with a repair option, never silently remove that restriction and show all tasks. Validate field/operator combinations and bound query complexity. Never interpret predicates as raw SQL.

CLI list/get/create/update/delete/query uses the same API and predicate engine. Paginate results and provide truthful total counts. F2 boards may use a saved view without storing independent workflow data.

Acceptance: F7-A verifies GUI/CLI parity, mixed filters, labels any/all, and persistence; F7-B covers rolling dates and timezone boundaries; F7-C covers missing references, invalid predicates, owner isolation, and deletion without task loss; F7-D confirms built-in views and pagination remain correct.

## 11 API and data evolution

The following are proposed API families. Confirm exact names against live routes before implementation and update the API contract; avoid collisions with existing Plans and system views.

| Capability | Proposed API addition | Persistence or contract change |
|---|---|---|
| F1 | `/handoffs/propose`, `/handoffs/apply`, `/handoffs/receipts/{id}` plus key lookup | Versioned graph; owner-scoped idempotency receipt; source metadata |
| F2 | Task workflow fields and `/tasks/{id}/workflow` transition | Open workflow state, waiting note, board rank/revision; shared completion service |
| F3 | `/schedule/runs/{id}/explanations`, task latest-explanation lookup | Structured calculation outcomes with input/algorithm provenance |
| F4 | `/focus-windows/{id}/overrides` and override CRUD | Dated replacement bands, strictness, stored timezone |
| F5 | `/templates`, versioned template proposal and apply | Built-in definitions; F1 instance receipt reuse |
| F6 | `/schedule/previews`, `/{id}`, `/{id}/apply` | Immutable proposal, input revision/fingerprint, expiry, apply receipt |
| F7 | `/views` user CRUD and `/{id}/tasks` | Versioned SavedFilter predicate and presentation fields |

Use existing error envelopes and CLI exit codes. Stable new conflict codes include idempotency mismatch, stale preview, and conflicting board revision. Validation errors should identify the entity/field and preserve the distinction between bad input, missing resource, and conflict. Unknown or foreign IDs must not disclose another owner's metadata.

Use additive migrations and explicit backfills. Migration numbers must follow the actual current head, not a number assumed by this document. Preserve existing completion, recurrence, inheritance, and API clients. Do not require board states on old clients. Document any unavoidable compatibility change before introducing it.

## 12 Implementation slices and verification handoff

Deliver in the agreed F1–F7 order. Shared internal foundations may land early when they directly support the current slice: F1 supplies template application; F2 defines workflow filtering; F3 separates calculation from application for F6; F4 adds override inputs to that calculation. Do not use those relationships to reorder the user-facing priorities without discussion.

For each slice, provide a compact delivery record:

| Field | Required content |
|---|---|
| Build | Commit/revision, migrations, deployment environment |
| Scope | Acceptance IDs implemented, remaining items, meaningful departures from design defaults |
| Automated evidence | Exact command, result, test count, environment, and artifact/log location |
| Integration evidence | Relevant API/CLI/UI path tested together, including error cases |
| Manual verification | Short reproducible checklist, expected outcomes, data prerequisites, current status |
| Known limitations | Specific impact and agreed disposition; no silent conversion into pass |

Track **implemented**, **automated checks passed**, **integration verified**, and **manual verification pending/passed** separately. Trish owns the sequencing of her manual validation; the team supplies usable cases rather than requiring her to reconstruct the intended behavior.

Run focused tests during implementation and a combined automated regression pass after integration. At minimum cover API and CLI tests, frontend type/build checks, migration upgrade on representative existing data, and meaningful browser interactions for the new board and preview. Migration/recovery exercises and destructive test cases belong in an isolated database. Never seed, purge, or manipulate household credentials in the daily-driver database for these checks.

### Combined acceptance scenarios

1. **Idea to usable project:** Apply an F1 handoff with source link and manual schedule policy; inspect its F2 board; use the CLI to move a task and the GUI to read it back. Retry the handoff and prove no duplication.
2. **Coursework without schedule flooding:** Instantiate a course, exclude optional items, inspect labels and module structure, and deliberately enable inherited scheduling only when requested. No unrelated project policy changes.
3. **Disrupted week:** Add an F4 map-specific override, read an F3 explanation, generate an F6 preview, inspect the changes, and apply. A task bound to another map remains unaffected by that override.
4. **Concurrent work:** Generate a preview, change a relevant task through the CLI, and attempt apply in the browser. Get a stale conflict with no schedule mutation. A repeated successful apply returns its receipt.
5. **WIP and timing remain independent:** Move scheduled work into In progress and Waiting; confirm dates and scheduling eligibility remain unchanged. Complete a recurring task and verify the next occurrence is Ready.
6. **Find it again:** Save an owner-wide WIP view with rolling dates; query it through the CLI and board. Check pagination totals, missing-reference behavior, and isolation from another household account.

## 13 Decisions to retain during implementation

- All seven features are committed scope, not a speculative menu. Desktop packaging is excluded.
- Kanban is included because Trish already uses that visual model for WIP. Do not downgrade it to optional polish.
- Replan preview precedes saved views.
- A small Coursera family is sufficient; preserve supplied course content and reuse the importer.
- The CLI serves Trish at a terminal as well as assistants. JSON reliability and useful human-readable output both matter.
- Existing source links and receipts provide continuity. No new Slack setup or collaboration-suite infrastructure is required.
- Manual validation may follow development. Evidence must remain accurate, and concrete risks should be raised candidly rather than treated as a reason for blanket process gates.

### Proposed defaults to call out in the first team handoff

Ready/In progress/Waiting/Done columns; Waiting has no implicit scheduling effect; manual policy for new bulk handoffs/templates; fixed columns without WIP enforcement; specialization/course/module as the three templates; map overrides replace bands within global work capacity; preview applies the complete proposal and expires after 15 minutes. These choices are visible and revisable. They do not reopen the agreed seven-feature scope.
