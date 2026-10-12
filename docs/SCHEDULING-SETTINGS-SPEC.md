<!--
==============================================================================
  File: docs/SCHEDULING-SETTINGS-SPEC.md
  Description: Scheduling and Settings design handoff, including Assist and CLI parity.
  Component: Scheduling / Settings / Assist / CLI
  Version: 1.4.4 (Approved product contract)
  Created: 2026-10-12
  Last Update: 2026-10-12
==============================================================================
-->

# Scheduling and Settings pass

**Status: approved product contract for the next version's Scheduling/Settings pass** (Trish, 2026-10-12). Hygiene **exited** 2026-10-12; **S1 first slice** (contract §10) **landed** with Renee Quality **PASS** on migration tests (§10 item 7) — [delivery/0.7-S1-FIRST-SLICE-2026-10-12.md](delivery/0.7-S1-FIRST-SLICE-2026-10-12.md). **Full S1 / 0.7.0 train not Closed/shipped.** **Decision ledger and rationale:** [Dex discovery review v1.18](redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md).

**Version (locked Trish 2026-10-12):** product SemVer **`0.7.0`** for this Scheduling/Settings train (subtitle OK: “Scheduling & Settings”). Micro follow-ups may ship as **`0.7.x`** (e.g. `0.7.5`). Path to **`1.0`:** on the order of three more major chunks after this train — not a promise of calendar dates. Hygiene starting tip = commit that opens **`0.7.0`** work and aligns API/CLI/web/desktop to a **single shared product version** (retire today’s `0.0.0` / `0.1.0` disagreement); tip SHA when hygiene opens.

This specification consolidates Trish's requirements from [DEF-032–033 and DEF-036–041](DEFECTS.md), including context modes as part of a substantial version update. Product choices below are **approved** unless marked **operational TBD** or **V.Next-Not-Now**. Existing behavior is evidence for migration, not the target contract.

## 1. Outcome

thePlan should accommodate business and personal activities, changing work schedules, and combinations of scheduling requirements without making the operator translate everyday intent into implementation details. It should be useful before customization and clear about its default assumptions.

An operator can say, “I usually do coursework in the evenings, but only when I'm home,” establish the missing details, review the resulting configuration, and inspect its scheduling effect. The same configuration can be managed through the UI, built-in Assist, or Julie using supported CLI commands. One backend owns validation, inheritance, eligibility, ranking, and explanations.

### Design principle: support working styles, not prescribed methodologies

Support how people actually work without requiring them to subscribe to a particular productivity methodology, including Trish's own hybrid approach. Contexts, priorities, estimates, and scheduling rules should be understandable and useful without knowing GTD or any other named system. Users may combine these capabilities to suit their practices; the app must not require methodology-specific terminology, rituals, or workflow stages to perform ordinary planning and scheduling.

Trish's scenarios are concrete acceptance examples, not a universal workflow imposed on other users. Preserve useful defaults and optional configuration without turning personal preferences into mandatory process. During design review, ask: “Would this capability still make sense to someone unfamiliar with the methodology that inspired it?”

This is the current product boundary, not a permanent prohibition. Methodology-specific features may be reconsidered through an explicit future product decision by Trish, with their usability cost, scope, and implementation effort assessed before inclusion. They are not implicitly authorized by this pass.

**Methodology-neutral foundation; optional methodology-informed starting points.** Future presets may arrange shared capabilities such as saved views, defaults, and enabled features. Choosing a methodology must remain optional; ordinary defaults must be sufficient to begin using the app. Presets are editable starting points, not compliance modes: users may adopt selected elements, combine approaches, or freely alter them without warnings that they are using a methodology incorrectly. Trish explicitly reserves the right to adapt any methodology to her own needs.

**Deferred beyond this pass:** methodology presets, their catalog, and their setup/apply UI. Future design should favor one shared capability model, preview configuration changes before applying them, and avoid silent reorganization of work or changes to scheduling rules. This direction does not require building a preset framework during the scheduling/settings pass.

## 2. Scope and traceability

| Source | Required outcome |
| --- | --- |
| DEF-032 / DEF-036 | Human-friendly durations; effort, elapsed time, calendar intervals, and workdays have explicit meanings. |
| DEF-033 | Coherent Settings organization, useful defaults, contextual access, and discoverable scheduling preferences. |
| DEF-037 | Actual selected working days, per-day hours, and dated changes to a recurring baseline. |
| DEF-038 | Weekday/weekend distinctions separate from working/nonworking availability; personal hours are not vetoed by business hours. |
| DEF-039 | Conversational configuration, composable requirements/preferences, explicit exceptions, and understandable conflicts. |
| DEF-040 | Complete external-agent CLI workflow without raw API, database, browser, or custom-script workarounds. |
| DEF-041 | Configurable context defaults, reusable user-defined modes, planned context timeline, and calendar/travel interaction. |

DEF-031/034/035 (drag flow and support breadcrumbs) are adjacent calendar work. Coordinate interfaces with them, but do not silently absorb them into this pass. General post-refresh cleanup, location tracking, autonomous activity inference, and an unrestricted agent execution system are out of scope. General labels do not acquire scheduling effects implicitly.

## 3. Current implementation and migration constraints

Verified in the local repository on 2026-10-12:

- `scheduler/placement.py`: global eligibility is `day.weekday() < workweek_days`, with one start and duration applied to workdays. Time Map bands are clipped to those bounds.
- Time Map bands select individual weekdays and carry green/yellow/red tiers. Non-strict maps permit neutral fallback; strict maps require allowed bands. Red exclusions apply across placement tiers within the selected map.
- `scheduler/windows.py`: one effective map is selected task > project > epic. This is replacement inheritance, not independent rule composition.
- A Monday/Wednesday band does not make the map assignment Monday/Wednesday-only. On unbanded days, non-strict maps permit neutral global availability; strict maps permit none. There is no per-day fall-through to the next ancestor's map.
- Temporary Time Map overrides replace bands/strictness for their effective date range. They are not additive rule composition.
- CLI: epic/project map assignment, temporary overrides, schedule preview and explanation exist. Standing map CRUD/discovery, direct task assignment, explicit clearing, and new rule configuration are incomplete or absent.
- Assist's action schema currently supports task/project creation, not map/rule configuration.

Preserve existing schedules and interpretation during migration. Do not reinterpret every existing task-level map as an additive constraint. Discovery must produce a compatibility table for legacy assignment, strictness, red bands, empty maps, overrides, and global bounds, including how an operator explicitly opts into new behavior. The version installed in Julie's environment needs separate verification.

## 4. Concepts and shared rule contract

### 4.1 Separate amount from placement

An effort estimate answers “how much work?” Availability and rules answer “when may it happen?” A workday-sized estimate can be split across eligible dates according to existing block rules. It does not require one full shift per calendar date.

Distinguish:

- Calendar weekday: Monday through Sunday; weekday/weekend groupings are named selections, not synonymous with work.
- Working availability: selected work dates and hours, including Tuesday–Saturday or variable shifts.
- Personal availability: declared time suitable for personal activities, including evenings, weekends, and nonworking weekdays.
- Context availability: effective location/resources from configurable defaults, explicit modes, and calendar evidence (section 4.5). A default is an assumption with provenance, not an explicit declaration. Unresolved contradictions are not permission to schedule.
- Requirements: conditions every eligible candidate must satisfy.
- Preferences: ranking among eligible candidates, never permission to violate a requirement.

These are conceptual distinctions, not a mandate for a database table per term.

### 4.2 Combination and conflict handling

**Scheduling language (approved):**

- **May schedule during…** — permitted alternative availability windows (e.g. Work or Personal). Alternatives **union**.
- **Must have…** — independent requirements (e.g. Home and a usable computer). **All** must hold (intersection).
- **Prefer…** — ranking among otherwise eligible times (e.g. evenings). Does **not** create availability or waive a requirement.

Explicit scheduling assignments may inherit from project or epic with **source visible**. Ordinary descriptive labels do not silently grant scheduling permission. Relevance to both Work and Education does not by itself authorize consuming working hours.

**General availability (approved):** Editable policy independent of Work and Personal. Tasks with no explicit or inherited assignment use **General**; show that provenance. Do **not** auto-union all Work and Personal hours for unclassified tasks. Existing accounts: seed General from current scheduling days/hours while preserving effective eligibility. Fresh accounts: **Monday–Friday 09:00–17:00** in the user's timezone as a visible, editable starting schedule (not an employment classification). Fallback tasks link to General rather than copying its hours; settings save does not automatically move blocks. If General offers no usable time, explain the failure — do not borrow another policy's windows.

**Purpose defaults (approved):** Unclassified tasks use General (above). Multi-purpose association uses the approved combination rule in acceptance (union of permitted windows vs independent requirements — document in fixtures SS-06/07 and purpose-combination cases). An ordinary label named Work must not change scheduling merely because of its name.

**Eligibility stack:**

1. Resolve applicable assignments, origins, dates, weekday scope, and explicit replacement/exception operations. **Resolve authorized scoped exceptions into effective inputs before evaluating the stack** (section 4.4). Each exception changes only its named rule and scope; later layers do not invent additional permission.
2. Determine declared eligible availability. Business working hours cannot act as an undocumented universal cap on personal work.
3. Intersect applicable requirements and subtract applicable exclusions, busy time, and other existing hard constraints.
4. Rank remaining candidates using preferences and the approved normal ranking policy (below).
5. If none remain, preserve the unscheduled result and explain why. Never silently relax a requirement.

Multiple windows within one availability source may offer alternatives (union); independent required sources combine by intersection. Red exclusions retain priority within their applicable scope; rules on unrelated work do not create global blackouts.

“Usually” is a preference unless clarified otherwise. “Only” is a requirement. Ambiguous wording prompts a targeted question. Existing prerequisites, deadlines, capacity limits, buffers, pins, manual tasks, and placement granularity continue to matter.

**Normal ranking (approved):** Preserve existing task priority/deadline ordering; use preferences to choose among eligible placements. A preference must not cause an **avoidable** deadline miss — use an eligible afternoon fallback when preferred evenings cannot meet the deadline. When both placements meet the deadline, favor the preferred window provided that does not prevent a higher-ranked task from being placed. Hard requirements and pinned blocks stay protected; explain unmet preferences when deadlines or competing work determine placement. Use bounded behavior in the existing scheduler, not a global optimum promise. Capture concrete undesirable-placement examples in acceptance (fixtures **A1** / **A2** isolate preference vs requirement from ranking).

**Optional “Make it pretty” (approved boundary):** Separately scoped refinement may spend extra effort rearranging **movable** work after normal scheduling passes acceptance. **Not** a blocker for S1–S4 or core release closure. **Go/no-go:** after normal scheduling passes acceptance, Jim assesses remaining refinement work and brings Trish a concrete recommendation. If deferred at that gate, core delivery may close with refinement recorded as outstanding. If selected, refinement gets its own slice and quality gate. Shared API/CLI path and preview/apply contract live in foundations without making core delivery depend on refinement. Refinement: known preferences; focused question when improvement goal is unclear; protect hard requirements and pins; preview before apply with movement/deadline tradeoffs; bounded attempt; Julie included in schedule-change handoff when applied. See Dex handoff for narrative and examples.

### 4.3 Inheritance and day-scoped behavior

Show whether a rule is local or inherited and from which epic/project. Adding a rule is distinct from replacing an inherited rule. Clearing a local assignment restores inheritance and is **distinct** from explicitly permitting no time.

**Day-scoped operations (approved):** Support both **Change selected days** and **Only allow selected days/times** as distinct operations in UI, CLI, and Assist.

| Operation | Behavior |
| --- | --- |
| **Change selected days** | Replaces the targeted inherited window on selected days only. Outside that scope the rule does not participate; normal inheritance continues. Independent requirements and busy intervals still apply. Offer **one specific date** or **recurring weekday**; one-date changes expire to underlying schedule. Replacement removes the original window for that scope — does not silently add an alternative alongside it. |
| **Only allow selected days/times** | Hard eligibility requirement. Outside those days/times, automatic placement requires an explicit scoped exception. Active required rule with explicitly **no** permitted time → no eligible time; must **not** fall through to an ancestor. Deadline or high priority does not silently weaken the exclusive requirement. |

Separate three concepts for acceptance:

| Case | Intended interpretation |
| --- | --- |
| A rule is inactive on Tuesday | It contributes no restriction or preference on Tuesday; other applicable rules remain. |
| A required availability source is active Tuesday but has no windows | It offers no eligible time Tuesday (no fall-through). |
| Day-scoped **change** on Monday only | Monday uses replacement; other days retain inherited windows. |

Preserve legacy strict-map behavior until explicit migration/conversion. Include strict and non-strict legacy cases in acceptance. Fixtures **A1** (evening-only personal availability — no invented afternoon) and **A2** (explicit afternoon + evening — afternoon fallback with explained unmet preference) are required evidence.

Assignment scopes: epic, project, task. User-facing vocabulary remains a design choice; general-label attachment deferred until behavior and collision handling are approved.

### 4.4 Exceptions

Exceptions explicitly target a rule and scope: one task, a date range, or a standing-rule change. Make the action explicit: add a permitted window, replace a named rule, or waive a named requirement — **no** generic ignore-all-restrictions operation. An exception affects only its stated rule, task/date scope, and duration; expiry or removal restores underlying policy. It does not implicitly clear busy time or unrelated requirements.

**Resolve authorized scoped exceptions into effective inputs before evaluating the eligibility stack** (section 4.2). Example: business task normally ineligible on Monday; approved exception permits that task on one specified Monday only — does not permit other tasks, alter future Mondays, clear busy events, or waive independent context requirements.

Show consequences before saving. Temporary exceptions expire into the recurring baseline. **Overlapping dated availability (approved):** never save-order or implicit shortest-range-wins. Additions to the same policy combine (overlap counts once). Replacements targeting the same policy and dates require explicit resolution of which replaces which. Addition-over-replacement requires an explicit choice whether the extra window survives. Reject unresolved conflicts atomically; preserve draft; leave saved configuration unchanged. Empty replacement closes targeted availability without fall-through; expiry/removal restores underlying arrangement (preview that consequence).

Home availability follows the context timeline in section 4.5. Configured baseline supplies Home/computer/phone unless overridden or contradicted. Calendar/travel integration is part of this pass; automatic physical location tracking remains out of scope. **V.Next-Not-Now:** calendar-based and device-based location-aware errand suggestions (Dex handoff) — no implementation in this pass.

### 4.5 Context modes and timeline

**User requirements:** provide a presence-like Context control for declaring circumstances now or planning them in advance. Manual context intervals have a minimum duration of 30 minutes. Show intervals unobtrusively on the calendar, such as a thin colored bar; final visual treatment is a design decision. Include a readable label/details on hover and keyboard focus, and do not convey meaning through color alone.

Provide editable presets and user-defined reusable contexts: Home, At work, At theatre, Away, Travel, or others. Names are not hard-coded scheduling logic. Separate location, usable resources (computer/phone), and availability for tasks. Possessing a device does not make busy time free. A named place such as work must not inherit generic Away restrictions merely because it is outside home.

**Configurable initial default:** Home, computer available, phone available when nothing more specific is set and no calendar evidence contradicts it. This is Trish's requested starting point, not a claim that every user's life matches it. Users can change baseline location, resources, and context presets without code changes. Defaults need not be configured before first use. Migration must not silently move existing scheduled work.

For generic away appointments and travel, assume unavailable unless the user explicitly supplies suitable resource/access information; an explicit phone/computer declaration does not clear an appointment's busy status. At work can offer computer/phone and free gaps for eligible work or permitted calls. At theatre can offer its configured resources in free gaps, never treating a performance as free merely because a phone is present.

Proposed context fields: stable ID/name, location category or reference, usable resources, allowed activity purposes, and applicability interval/recurrence. Implementation chooses the actual schema. Reusable presets can populate a declaration, with interval-specific adjustments. How preset edits affect existing declarations is **approved** under **Editing presets in use** below (not an open discovery question).

Support both a one-off planned week away and regularly occurring contexts. A trip can establish an Away baseline with phone access and narrower computer-access windows. At expiry, return to the underlying context; do not blindly return Home when another planned mode still applies. Define recurring rules, bounded overrides, overlap conflicts, timezone/DST behavior, cancellation and editing of one occurrence in S0.

**Context precedence (approved):** Resolve location, usable resources, permitted activities, and busy/free status **separately**. A resource declaration must not erase occupied time.

1. **Configured baseline** — defaults where nothing more specific applies.
2. **Recurring context** — replaces relevant baseline assumptions during its hours.
3. **Dated context** — overrides recurring context for its declared period.
4. **Reliable event and travel information** — overrides conflicting location assumptions; accounts for occupied time. Ambiguous/generic meetings supply **busy only**, without invented location or commute.
5. **Explicit scoped correction** — corrects identified information for stated scope (e.g. virtual/Home for an appointment does not clear busy).

Additional rules: place change must resolve resources (generic Away must not inherit Home computer access). Same-level conflicts are **surfaced**, not last-write-wins. At expiry, restore underlying context effective at that time (appointment ending during week away restores trip context, not automatically Home). Context suitability does not create scheduling availability or waive task requirements.

**Travel scope (approved):** Ship **explicit event travel allowances**; preserve extension point for later reusable place-to-place matrix. **Defer** matrix implementation/CRUD and standing/default commutes. Different before/after durations; exact boundaries; overlapping travel intervals count shared time once. With event allowances alone, do not claim verified feasible routes between successive appointments.

Calendar derivation must use reliable event metadata or explicit operator mapping. Assist can ask about ambiguous event context.

**Concrete timeline fixture:** default Home/computer/phone; off-site appointment 14:00–16:00 with 30 minutes travel each side → Away/unavailable 13:30–16:30. Off-site board meeting 19:00–20:30 with 20 minutes each side → Away/unavailable 18:40–20:50. Travel consumes placement capacity. Between spans, restore underlying baseline. Derived 20-minute travel keeps exact boundaries; 30-minute minimum applies to **manual** context declarations.

**Retirement and deletion (approved):** Retire by default; explicit migration or removal of active uses before delete. Retirement removes from new-assignment choices while preserving existing assignments and behavior. Replacement with compatible item: preview + atomic migration. Explicit assignment removal only with inheritance/fallback preview — never silently broaden availability through deletion. Delete unused only when no active references; preserve historical explanations. Declaration removal ≠ preset deletion. Recheck references under concurrency on apply.

**Editing presets in use (approved):** **Save preset only** (existing declarations unchanged) or **Save and update selected future uses** (atomic). Preserve declaration overrides by default (“Local override retained”). Recurring future occurrences updatable from effective date; past and in-progress occurrences unchanged unless explicitly selected for current occurrence. Expose preset revision provenance.

**Task alignment:** distinguish purpose (Work, Education, Theatre), resource requirements, location requirements, and time preferences. A Work epic/project can supply scheduling rules for its tasks. Work at home and At workplace can both permit Work activities; “collect office equipment” may additionally require the workplace. User-configured activity/context relationships must be explicit; an ordinary label named Work does not silently become a scheduling rule. This alignment must use the shared composition and inheritance contract, not a second context-specific scheduler.

Context says what circumstances apply; task rules say what circumstances are suitable; calendar occupancy and other constraints determine whether time is free. The Context control is not a continuous-location sensor and does not automatically apply a replan. Context changes invalidate affected preview inputs and are reflected in effective and historical explanations with provenance.

## 5. Duration entry and defaults

**Duration input (approved):** Accept friendly hours/minutes consistently across UI, CLI, and Assist (`90m`, `1h 30m`, `1.5h` → 90 minutes). Explicit fractional workdays use current nominal conversion with visible save-time conversion. Bare number in a field labeled minutes means minutes; conversational input clarifies when units are unclear. Ambiguous effort shorthand such as `2d` requires clarification — not silent workday or 48-hour conversion.

Convert complete input before rounding once to nearest whole minute (exact halves round up); show normalized values when rounding changes them. Reject negative durations; correct effort through correction workflow. Positive input rounding to zero → request at least one minute. Zero valid for remaining effort and buffers, not block-size bounds or new time-worked entries. Blank optional bounds inherit defaults, never zero or unlimited; unlimited maximum remains explicit. Preserve effort precision independently of placement grid rounding.

**Nominal workday conversion (approved):** Separate from scheduling availability. Changing working hours or nominal workday setting does **not** change how much work an existing task requires. One workday = configurable effort amount; new accounts **8 hours**; existing accounts may seed from current workday-length during migration. Convert to stored minutes at save (`2 workdays` at 8h → 960 minutes); later nominal change does not rewrite stored estimate. Show conversion before save; explicit re-estimation in workdays uses then-current conversion visibly; unrelated edits do not reconvert. Use “workday” for nominal effort and “day” for calendar/date ops; “tomorrow” advances local calendar date.

**V.Next-Not-Now:** week/month **effort** units — retire silent fixed w/mo conversions; clarify requests; do not alter saved estimates. Calendar-date expressions (“due in two weeks”) remain separate.

Both elapsed day (24h) and calendar-date arithmetic remain distinct from workday effort. Do not silently dual-purpose workday-length field for availability and nominal conversion.

New installations: usable defaults without questionnaire; General availability and context baseline per sections 4.2 and 4.5. Existing users: equivalent effective behavior until change; explicit migration into context and General models.

### 5.1 Task chunking and progress (approved)

Deliver block-size controls and effort-progress through shared UI and CLI (existing DB fields alone are not delivery).

**Bounds:** Omitted min/max inherit user default with source shown; explicit task overrides one bound. Explicit **No limit** maximum distinct from omission. “Keep in one block” requires all remaining work in one continuous eligible window. Validate effective bounds together — conflicting min/max requires correction. Final remainder may be smaller than minimum; buffers separate from work duration.

**Quantities:** Original estimate (retained); time worked (explicit only, never inferred from elapsed block); remaining estimate (drives scheduling).

**Progress UX:** Enter time worked; suggest remaining reduced by effort, editable before save. Remaining-only re-estimation allowed; completion without every minute logged; zero remaining offers explicit completion — logging effort does not silently mark Done; missed session does not reduce remaining. History with corrections; duplicate-safe logging; progress changes stale previews without silent rearrange. Display e.g. “2h worked · about 6h remaining.”

**Pinned reservations:** Future pins reserve part of **remaining** work, not completed effort. Past blocks are not completion evidence. Excess reservation vs remaining → surface mismatch.

**Operational TBD (pre-S1):** Migration contract for existing tasks, in-progress block boundaries, and progress initialization without inferring past work — **closed in-repo** at [delivery/0.7-S0-MIGRATION-CONTRACT.md](delivery/0.7-S0-MIGRATION-CONTRACT.md) (2026-10-12); see also Dex handoff and section 12.

## 6. Settings and task UI

**Required:** Settings must have tabs or equivalent focused section navigation, not one monolithic scrolling page. Users can open the section relevant to their current task. Section switching and contextual entry must preserve drafts or offer an appropriate dirty guard. Navigation must be usable by keyboard and on narrow screens; a contextual link should open the relevant section directly. Exact tab/rail/page structure remains a design choice.

Proposed Settings grouping: availability and working schedules; scheduling defaults and duration conventions; Time Maps/rules and temporary exceptions; account/calendar connections; appearance and other preferences; **About** (product identity). Inventory current controls before finalizing navigation. Keep frequent contextual entry points into the same editors; avoid duplicate settings with independent state.

**About (approved for S3 Settings tabs work):** A focused Settings section (or equivalent tab) shows thePlan’s **official product version** and related identity so the operator (and Julie) need not scavenger-hunt package metadata. Minimum: product name, SemVer product version (**`0.7.0`** when this train ships; show the running build’s version string from a **single shared source** — not three disagreeing package.json values). Optional: short build/git tip in non-production, link to docs or release notes. CLI `theplan version` and any API identity endpoint must report the **same** product version string. Aligning package versions to that source is part of hygiene / S3 delivery, not a separate product debate.

Availability editing supports selected days, per-day hours, dated replacement schedules, **multiple windows per day**, and **explicit overnight windows** (approved). Split windows (e.g. Mon 09:00–12:00 and 14:00–17:00) offer alternatives; gaps stay unavailable; task splitting rules determine whether effort spans blocks — one continuous block cannot bridge a gap. Overnight: explicit “ends next day”; start day identifies recurring window; equal start/end must not silently mean zero or 24h. Replacing Monday overnight occurrence replaces full occurrence including Tuesday tail (show scope in editor). Midnight crossing allowed when entire interval eligible. Windows in **configured schedule timezone**, not browser; wall-clock preserved across DST; elapsed minutes for effort.

**Daylight-saving (approved):** Shared deterministic resolution in schedule timezone across scheduler, UI, CLI, Assist — gap boundaries move to first valid instant after gap (not shift whole window to preserve duration); skipped zero-duration occurrences explained. For **recurring** ambiguous (fold) boundaries, default to the **first** occurrence consistently for start and end, with an optional explicit second-occurrence override. For an **explicitly entered one-time** ambiguous boundary, require the user to choose first or second occurrence and show the timezone offset; preserve the resolved exact instant. One-time nonexistent boundary flagged with a valid replacement offered before save; effort counts elapsed minutes. Acceptance fixtures in Dex handoff.

Preview affected dates, timezone, baseline resumption, and DST adjustments in preview/explanation.

Task details provide an effective-rules summary with origin, strength, scope, and exception indicators. “What affects this task?” is available before a scheduling run; “Why this placement?” records the inputs and outcome of a particular run. Distinguish live configuration from historical explanation and mark stale results.

Editing configuration does not itself move blocks. Show that a preview/replan is needed, and offer the existing Preview changes flow. Audit background dispatch paths so saving configuration cannot cause an unintended replan through another writer. An already-running or old preview must not apply results based on obsolete configuration.

## 7. Shared API, revisions, and operations

Implementation chooses endpoint names and persistence design after discovery, but must provide:

- Owner-scoped discovery, read, create, edit, and retirement/deletion behavior for maps/rules and availability schedules; no silent dangling references.
- Explicit assignment/add/replace/clear and scoped exception operations with validation.
- Effective configuration resolution, provenance, unknown inputs, and actionable conflicts in structured results.
- A reviewable configuration proposal with affected scopes, versions, and expected changes. Configuration apply validates the reviewed versions; stale input requires a refreshed proposal.
- **Atomic configuration apply (approved):** One approved proposal applies completely or none of its changes take effect; validate and commit as one transaction; failure rolls back with understandable error. Stale revision → reject and refresh. Idempotency: same key + intent replays receipt without duplicate effects; reject key reuse with different intent; distinguish saved / not saved / result unknown after connection loss. Configuration apply **separate** from schedule preview/apply; saving config invalidates previews but does not move blocks. Julie notification/handoff after successful save is **not** in the DB transaction — retry handoff without reapplying config (no new messaging integration authorized).
- Stable operation identity/idempotency for retries, including omitted defaults. Same intent replays; changed intent conflicts. Read-back and receipts expose committed IDs and revisions.
- Integration with schedule revision locking, preview stale checks, and explanation fingerprints. All newly relevant inputs participate, including assignments, rule definitions, context availability, exceptions, and timezone.

Configuration proposal and schedule preview are distinct artifacts: the former describes configuration writes; the latter calculates placement from committed configuration. First delivery need not simulate scheduling against uncommitted proposals, but the UI must not imply that it does.

## 8. Built-in Assist workflow

**Model (approved):** Keep **Llama 3.2** for the build; evaluate alternatives **after** the build (not a discovery/release prerequisite). Assist role: convenient everyday requests from phone (create task with duration, assign with inherited rules, propose away interval, explain unscheduled). More involved planning → Julie or Dex. Model replaceable via configuration; test during build; unresolved failures visible. Post-build comparison against bounded shortlist (e.g. Qwen3.5 9B as initial candidate only) on real scenarios — no model switch requested by Dex handoff. Remote Assist via thePlan API; ordinary task management usable if Assist unavailable.

Assist interprets intent and proposes structured changes; shared services resolve inheritance, validate, calculate placement, apply authorized changes. Configuration approval ≠ schedule application.

1. Receive intent, e.g. “I usually do coursework in the evenings.” Retrieve only relevant settings and work scopes.
2. Ask for missing days/hours, preference strength, and target work. Reuse answers already supplied. Resolve ambiguous names without guessing.
3. For “only when home,” inspect the context baseline, planned declarations, and calendar contradictions. Explain default assumptions; ask only where required information remains ambiguous. Do not ask for a full home schedule when the configured default already supplies it.
4. Propose reuse or creation of configuration. Show timezone, strengths, dates, assignments, inherited overrides, and impact. Do not duplicate equivalent maps unnecessarily or silently edit a shared map used by unrelated work.
5. Apply the reviewed configuration within authorization; return a readable receipt and effective result.
6. Offer schedule preview, explain any conflict, and apply scheduling only within the user's authorization.

Example proposal: “Prefer coursework Sunday–Thursday, 19:00–21:00; require Home context; attach to Education. Home is your default except where planned context or calendar evidence overrides it. These projects inherit it; these tasks have explicit replacements. Save these preferences?” Follow with a separate preview/apply choice. A model failure, malformed output, or timeout must not partially apply configuration or discard the human's draft.

Assist interprets intent and explains results; backend validation and scheduling determine semantics. Explicit requirements cannot be weakened by model discretion. Its context is task-relevant, not a biographical interview.

## 9. Julie's supported CLI workflow

**S1 CLI delivery (approved):** **Skip early partial CLI map CRUD.** Deliver the supported **full** interface through the shared API/CLI plan, including local installed-CLI and Julie-on-supernova acceptance gates. Partial map CRUD as an early release is superseded.

**Collaborator workflow (approved):** Supported workflow is **Trish, Julie, Dex, and Assist** — not Julie alone. Routine maintenance delegable; judgment calls return as focused choices. Shared validated services; receipt with what changed, effective rules, unresolved items. Keep Julie informed on schedule-oriented configuration and replans; distinguish configuration from calendar placement. Coordination requirement, not automatic messaging integration.

**No workarounds required.** Completion cannot depend on raw HTTP, database editing, custom helper scripts, browser-only controls, or Trish fetching IDs. Human clarification and authorization are normal parts of the workflow.

CLI capability contract (command names to be proposed, not existing syntax):

| Capability | Required behavior |
| --- | --- |
| Discover/read maps, rules, availability, relevant settings | Search/list with pagination, stable IDs, structured output; ambiguity reported. |
| Create/edit maps and availability | Same validation and semantics as UI, including bands, days, timezone, strengths, and temporary changes. |
| Assign/add/replace/clear | Epic/project/task scopes; explicit clearing restores inheritance; effective-state read-back. |
| Review/apply configuration | Machine-readable proposal and receipt, version checks, safe retries, shared API contract. |
| Inspect effective rules | Origins, applicable dates, unknown context, conflicts, legacy interpretation. |
| Preview/explain/apply schedule | Extend existing commands and stale handling; no automatic apply merely from configuration writes. |

End-to-end: Trish delegates coursework setup to Julie. Julie discovers current state, asks only for missing decisions, presents the configuration, applies authorized changes through supported commands, verifies read-back, creates a schedule preview, reports outcomes/conflicts, and applies it only if authorized. Exercise this from the CLI actually installed in Julie's environment, including upgrade/version compatibility. Library-level tests alone do not close this scenario.

Built-in Assist and Julie need not share conversational machinery. They must share the same configuration operations and effective scheduling result.

Context parity is required: both can discover/edit defaults and reusable modes, create/edit/cancel planned or recurring declarations, inspect derived event/travel intervals, manage explicit scoped corrections, and read effective context/provenance through supported operations. Julie's acceptance scenario includes planning a week away with phone and selected computer-access windows, then previewing coursework/work placement. No browser-only context setup step is acceptable.

## 10. Acceptance matrix

All rows initially **Open**. Renee should keep automated evidence separate from browser/installed-CLI evidence and Trish's acceptance. Each fixture records timezone, availability, rules, other constraints, and expected candidates.

| ID | Scenario and required evidence |
| --- | --- |
| SS-01 | Fresh setup is usable with approved defaults; existing setup migrates without changed effective availability or block movement. |
| SS-02 | `2h 30m` saves as 150 minutes and displays readably in UI/CLI; malformed/negative input is rejected without draft loss. |
| SS-03 | Day/workday distinction and approved conversion are visible; variable shifts and later default changes do not silently alter saved effort. |
| SS-04 | Tuesday–Saturday work, per-day hours, and a dated roster work as specified; baseline resumes after the exception. |
| SS-05 | Personal weekend/evening work remains eligible without changing the business schedule to seven days. |
| SS-06 | Prefer evenings + require home: evening overlap wins; if only afternoon home time exists, it remains eligible and missed preference is explained. Include **A2** (explicit afternoon fallback). Normal ranking: preference must not cause avoidable deadline miss; higher-priority tasks protected. |
| SS-07 | Require evenings + require home, no overlap: unscheduled with both causal constraints identified; no silent relaxation. Include **A1** (evening-only availability — no invented afternoon). |
| SS-08 | Unspecified context uses configurable Home/computer/phone baseline. Derived contradictions and explicit declarations override it; unresolved ambiguity and known-unavailable time remain distinguishable from default assumptions. |
| SS-09 | Add, replace, clear-to-inherit, and explicit exception yield approved outcomes; legacy task > project > epic behavior is preserved on migration. |
| SS-10 | **Change selected days** vs **Only allow selected days/times**; one-date vs recurring change; Sunday-night-style exclusive restriction; empty required vs cleared assignment. Legacy strict/non-strict maps on migration. |
| SS-11 | Competing preferences under approved normal ranking; unrelated maps do not exclude this task. Optional **Make it pretty** evidence separate if Jim go/no-go selects implementation. |
| SS-12 | Scoped exception changes only intended work/dates; expiry restores baseline; shared-map impact is visible before edits. |
| SS-13 | Timezone, DST gap/fold/ambiguous fixtures, overnight/split windows, temporary override boundaries — agreement across scheduler, UI, CLI, Assist. |
| SS-25 | Duration equivalents, fractional workdays, rounding, negative rejection, zero remaining/buffer, ambiguous `2d`/w/mo clarification (w/mo deferred), effort vs grid rounding. |
| SS-26 | Chunking bounds, keep-in-one-block, progress/time-worked/remaining, pins vs remaining, duplicate-safe logging, preview invalidation. |
| SS-27 | Dated availability overlap resolution; atomic reject on conflict; empty replacement and restoration. |
| SS-28 | Retire/replace/delete referenced maps and contexts; preset save-only vs update selected uses; stale apply under concurrency. |
| SS-29 | Atomic configuration apply: success, mid-failure rollback, stale rejection, idempotent retry, handoff failure after commit. |
| SS-30 | **Buffer verification (requested):** 0/5/10 min between auto blocks; before/after pinned and external busy events; split-block policy; travel allowance interaction; preview/apply agreement. **Pre-S1:** agree intended **policy** and **test plan** (no circular wait on full evidence). **S2:** run verification on the implemented scheduler and record results/defects. |
| SS-14 | Configuration saves do not move blocks; old/in-flight previews become stale appropriately; pins, manual tasks, busy time, prerequisites, and capacity retain their contracts. |
| SS-15 | Live effective-rule explanations and historical run explanations remain distinct; provenance and stale status are correct. |
| SS-16 | Assist completes the example with only necessary questions; malformed output/failure causes no partial writes; shared-map ambiguity prompts review. |
| SS-17 | Julie completes the full scenario using installed CLI only, including discovery, clearing, combined rules, conflict and exception handling, read-back, preview and authorized apply. |
| SS-18 | Duplicate retry, changed-intent retry, concurrent edits, deletion of referenced configuration, and cross-owner access have tested outcomes; no silent overwrite or partial success. |
| SS-19 | A different user changes baseline context/resources; effective rules and Assist explanations follow their settings, with no hard-coded Home/Work/Theatre names. |
| SS-20 | Planned week away plus recurring At work/At theatre modes and shorter resource declarations resolve by approved precedence; expiry restores underlying context; manual intervals enforce the 30-minute minimum. |
| SS-21 | Appointment/board-meeting fixture produces exact 13:30–16:30 and 18:40–20:50 Away/unavailable spans; 20-minute derived travel stays exact; virtual meetings do not invent travel. |
| SS-22 | Phone/computer presence does not free a busy meeting; permitted work/calls fit free At work gaps; work-at-home remains eligible; location-specific tasks still require the intended place. |
| SS-23 | Calendar context indicator is unobtrusive and readable without color; keyboard/narrow-screen access works. Settings uses focused sections with direct entry and draft protection. **About** section shows product name + official SemVer; UI, CLI `theplan version`, and API identity agree on one version string. |
| SS-24 | UI, Assist, and installed CLI produce identical context resolution and provenance; context edits stale old previews without moving blocks; event cancellation/rescheduling recalculates derived travel/context. |

## 11. Delivery sequence and responsibilities

| Slice | Deliverable / exit |
| --- | --- |
| S0 Discovery | **Exit:** Trish-approved product contract (this spec + [Dex v1.16](redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md)). Jim: schema/API + **migration contract** (progress init, in-progress pins, legacy block defaults/inheritance) before dependent S1. Renee: fixtures including A1/A2 and expanded rows. **Version locked:** **`0.7.0`**. |
| Hygiene | Dependency Hygiene for **`0.7.0`** exits before **S1**; align package/web/desktop versions to shared product version source; record tip SHA. |
| S1 Shared foundations | Availability/duration/rule schemas, validation, revisions, compatibility migration, effective resolution, General availability. Full API + **full CLI** contracts together — **no** early partial map CRUD slice. Migration and negative-input tests pass. **First vertical accepted** 2026-10-12 ([0.7-S1-FIRST-SLICE](delivery/0.7-S1-FIRST-SLICE-2026-10-12.md)); **S1 CLI parity vertical** Quality PASS 2026-10-12 ([0.7-S1-CLI-PARITY-2026-10-12.md](delivery/0.7-S1-CLI-PARITY-2026-10-12.md)) — not full S1. Remainder (legacy compat table, DEF-040 / Julie installed CLI, duration/effective beyond that slice) + UI still Open. |
| S2 Scheduler and explanation | Composition, scoped exceptions, normal ranking, day-scoped ops, context/travel (event allowances; matrix deferred), DST/overnight/split, chunking/progress, buffer policy verification (SS-30). SS-04–15, 25–27 automated where applicable. |
| S3 UI and CLI parity | Focused Settings sections including **About** (product version); task review surfaces; **complete CLI** over same services; context configuration homes (defaults, presets, declarations) in UI + CLI. Installed-CLI integration evidence; version string parity UI/CLI/API. |
| S4 Assist and integrated acceptance | Assist on Llama 3.2; conversational proposal/apply; full Julie scenario; collaborator receipts/handoff; regression and operator acceptance. Optional **Make it pretty** only if post–normal-scheduling go/no-go selects it — not required for core closure. Unfinished matrix rows remain Open in docs. |

Dependency slices, not calendar commitments. **Do not** close DEF-040 on partial CRUD. Maintain regression suites; boundary tests validate behavior.

## 12. Decision status

### Settled (product — Trish 2026-10-12, Dex v1.16)

May/Must/Prefer composition; General availability; purpose defaults; **Change selected days** vs **Only allow**; normal ranking + A1/A2 fixtures; optional **Make it pretty** with post-acceptance go/no-go; nominal workday separate from availability; duration parsing/rounding; w/mo effort units **V.Next-Not-Now**; chunking/progress and pin reservations; overnight/split windows; DST resolution; dated overlap atomic apply; retire/delete and preset-in-use edits; atomic configuration apply; five-layer context precedence; event travel only (matrix + standing commutes deferred); scoped exceptions before stack; full CLI (no early partial CRUD); collaborator workflow + Julie handoff; Assist on Llama 3.2 with post-build model evaluation; location-aware errand suggestions **V.Next-Not-Now**.

### Remaining operational (not product reopen)

| Item | Owner / note |
| --- | --- |
| **Hygiene starting tip SHA** | Version name **locked `0.7.0`**; tip SHA when hygiene opens; micro-passes may use `0.7.x`. |
| **Schema/API and migration contract pre-S1** | **In-repo** [delivery/0.7-S0-MIGRATION-CONTRACT.md](delivery/0.7-S0-MIGRATION-CONTRACT.md) (2026-10-12) — progress init, in-progress pins, legacy block defaults/inheritance, Working/General seed. |
| **Buffer semantics (SS-30)** | **Pre-S1 policy approved** 2026-10-12 — [0.7-S0-MIGRATION-CONTRACT.md](delivery/0.7-S0-MIGRATION-CONTRACT.md) §6.1 (v1.3). Test plan §6.2. **S2:** verify implemented behavior and record evidence — not a full SS-30 execution gate before S1. |
| **Make it pretty go/no-go** | After normal scheduling passes acceptance; Jim brings concrete recommendation. |
| **User-facing vocabulary** | Composable rules naming; general-label attachment still deferred. Design during S3. |
| **Legacy migration compatibility table** | [delivery/0.7-S1-LEGACY-TIME-MAP-COMPAT.md](delivery/0.7-S1-LEGACY-TIME-MAP-COMPAT.md) — explicit opt-in/conversion for strict maps, overrides, global bounds. |

## 13. Handoff and completion

S0 product discovery is **closed** at the contract level. Hygiene **exited**; S1 **first slice** implemented with migration-test Quality PASS — see [0.7-S1-FIRST-SLICE-2026-10-12.md](delivery/0.7-S1-FIRST-SLICE-2026-10-12.md). **S2** cutover and full S1/UI/CLI parity remain the active engineering path. A capability is **shipped** only when UI, API, full CLI, Assist (where in scope), migration, explanations, and acceptance evidence agree per phase gates — defects in [DEFECTS.md](DEFECTS.md) stay **Open** until Quality evidence.

Record phased exclusions (travel matrix, w/mo effort, errand suggestions, optional refinement if deferred) explicitly. Operator migrate to **`028`** is required before live DB picks up S1 schema; household DBs may still be at **`027`** until then.
