<!--
==============================================================================
  File: docs/redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md
  Description: Dex discovery review and decision clarifications for Jim.
  Component: Scheduling / Settings
  Version: 1.16 (Optional refinement release boundary clarified)
  Created: 2026-10-12
  Last Update: 2026-10-12
==============================================================================
-->

# Scheduling / Settings: Dex discovery review

**For:** Jim and the team; Trish retains product decisions.
**Status:** Trish approved the recommendations and follow-on decisions below on 2026-10-12. Product decisions are approved; existing discovery, hygiene, and implementation gates remain in force.
**Working plan:** `C:\Users\trish\.cursor\plans\scheduling_settings_discovery_ce6c2e9b.plan.md`
**Related spec:** [Scheduling / Settings spec](../SCHEDULING-SETTINGS-SPEC.md), v1.4 (approved product contract; stamped from this handoff).

## Assessment

The discovery plan is coherent. The earlier four clarifications are captured: distinct nominal workday conversion, explicit context delivery homes, hygiene and installed-CLI sequencing, and honest limits for any partial map CRUD release. Ambiguous calendar events remain busy-only without invented commute or location.

The original review below records the issues and rationale. The approved disposition and follow-on decisions at the end settle the choices discussed with Trish. Carry those decisions into the S0 packet and spec before dependent implementation.

## 1. Split evening coursework into two explicit fixtures

**Current ambiguity:** Case A permits personal scheduling only Sun–Thu 19:00–21:00, then describes falling back to afternoon Home time. The stated availability does not permit that afternoon.

**Recommendation:** Preserve the original case and add a separate fallback variant.

| Fixture | Setup | Expected result |
|---|---|---|
| A1: Evening availability only | Personal availability 19:00–21:00; require Home; prefer evening. No other eligible window within the test horizon. | If those evening windows cannot accommodate the task, leave it unscheduled and explain the limiting constraints. Do not invent afternoon availability. |
| A2: Afternoon fallback allowed | Explicitly permit both afternoon and evening personal windows; require Home; prefer evening. Hold other constraints constant. | When evening placement is unavailable but afternoon placement is feasible, afternoon remains a valid fallback. Explain the unmet preference. |

The fixtures should isolate preference versus requirement from the separate decision about ranking against priority and deadlines.

## 2. Define purpose defaults and combination behavior

**Current ambiguity:** “Union of applicable availability sources for that work’s purpose” does not yet specify the behavior of an unclassified task or a task associated with multiple purposes.

**Decisions needed:**

- What availability policy applies to a task without an explicit or inherited purpose?
- For Work plus Education, does the association permit either purpose's windows, or express two requirements that must both hold?
- How are these choices represented and explained without turning ordinary labels into implicit scheduling rules?

**Recommendation:** Use an explicit default availability policy for unclassified tasks. Represent alternative windows separately from independent requirements. Preserve existing effective behavior during migration rather than silently broadening or eliminating eligibility.

**Acceptance additions:** Cover an unclassified existing task, an unclassified new task, and a task with two purposes. Record the approved combination rule and expected eligible intervals. An ordinary label named Work must not change scheduling merely because of its name.

## 3. Make the travel-matrix scope explicit

**Current ambiguity:** The new deferred-commute paragraph assumes “Places + pairwise travel matrix in S2,” but this concrete feature is not described in the S2 deliverables or the current spec. Event-specific travel allowances and a reusable place-to-place matrix are different commitments.

**Decision needed:** Is the matrix part of this release, or is only an extension point being preserved for later?

**If included:** Add an explicit decision row, delivery scope, and acceptance coverage for:

- Directional travel times: A to B need not equal B to A.
- Unknown routes: missing information must not silently become zero travel or an invented duration.
- Successive off-site events: determine the actual transition rather than automatically assuming a return Home between events.
- Precedence between event-specific allowances and reusable route values.

**If deferred:** Preserve a suitable extension point without committing S2 to implementing the matrix. Keep standing/default commutes explicitly deferred.

The rough size estimates in the plan have not been independently validated by this review.

## 4. Resolve scoped exceptions before evaluating eligibility

**Current ambiguity:** “Later layers never invent permission earlier layers withheld” is a useful invariant, but could be read as prohibiting an explicitly authorized exception to an earlier availability rule.

**Suggested contract wording:**

> Resolve authorized scoped exceptions into the effective inputs before evaluating the eligibility stack. Each exception changes only its named rule and scope. Subsequent layers do not invent additional permission.

**Acceptance example:** A business task is normally ineligible on Monday. An approved exception permits that task on one specified Monday. It does not permit other tasks, alter future Mondays, clear busy events, or waive independent context requirements. Expiry restores the underlying policy.

## Requested disposition

The four items are accepted. A1/A2 are already reflected in Jim's updated plan. Use the decisions below to settle purpose behavior, travel scope, and exceptions; Page records the contract and Renee maps acceptance evidence. Existing hygiene and S1–S4 gates remain in force.

## Approved decisions from the follow-on discussion

### S1 preparation and CLI delivery

**Approved:** Skip early partial CLI map CRUD. Deliver the supported full interface through the shared API/CLI plan, including the previously approved local installed-CLI and Julie-on-supernova acceptance gates. Earlier discussion of a partial release is superseded.

Trish will have Jim and Page reconcile the working plan/spec and determine the version name and hygiene starting tip. The product decisions recorded here are settled; this does not waive the existing hygiene exit or authorize this reviewer to start implementation.

Before dependent S1 work, the team should finish the schema/API and migration contract, particularly progress initialization without inferring past work, treatment of in-progress pinned blocks without double counting, and preservation of legacy block settings as defaults/inheritance are introduced. Map the expanded decisions into acceptance coverage beyond the original fixture list as necessary. Keep optional refinement and explicit deferrals separate from required delivery. Bring back concrete behavioral tradeoffs or incompatibilities with approved requirements, rather than reopening settled decisions merely for implementation detail.

### Scheduling language and composition (item 8)

- **May schedule during...** selects permitted alternative availability windows, such as Work or Personal. These alternatives combine by union.
- **Must have...** states independent requirements, such as Home and a usable computer. All must hold.
- **Prefer...** expresses a preference among otherwise eligible times, such as evenings. It does not create availability or waive a requirement.
- Explicit scheduling assignments may be inherited from a project or epic, with their source visible. Ordinary descriptive labels do not silently grant scheduling permission. Relevance to both Work and Education does not itself authorize consuming working hours.

Example: coursework may use Work or Personal availability, must have Home and computer, and prefers evenings. Afternoon fallback requires an explicitly eligible afternoon window, as in A2.

### Day-scoped replacement versus exclusive day/time requirements

**Approved:** Support both **Change selected days** and **Only allow selected days/times**. They are distinct operations, exposed clearly in UI, CLI, and Assist.

- **Change selected days:** Replace the targeted inherited window on the selected days. Outside that scope, the rule does not participate and normal inheritance continues. Independent requirements and busy intervals still apply.
- Offer **one specific date** or **a recurring weekday** for that change. A one-date change expires back to the underlying schedule.
- Replacement removes the original window for that scope; it does not silently add an alternative alongside it.
- **Only allow selected days/times:** Apply a hard eligibility requirement. Outside those days/times, the task cannot be automatically placed without an explicit scoped exception.
- An active required rule with explicitly no permitted time provides no eligible time; it must not fall through to an ancestor and reopen the day. Clearing an assignment restores inheritance and is distinct from explicitly permitting no time.
- A deadline or high priority does not silently weaken the exclusive requirement. If no eligible slot remains within the evaluated horizon, leave the task unscheduled with an explanation and allow the user to authorize a specific exception.

**Acceptance examples:**

| Case | Expected behavior |
|---|---|
| Study normally uses evening windows; this Monday has rehearsal, so replace Monday study time with an afternoon window | Monday afternoon is eligible subject to remaining constraints; the targeted Monday evening study window is removed. Other days retain their study windows. |
| The same change is configured for this Monday only versus every Monday | The one-date change expires; the recurring change applies on each selected Monday. Neither changes unrelated weekdays. |
| A recurring task is restricted to Sunday night | No automatic fallback to another day/time. If Sunday night cannot accommodate it, report the conflict. An approved one-occurrence exception does not rewrite the recurring restriction. |
| Selected day explicitly has no permitted time; then the assignment is separately cleared | Empty required availability blocks placement under that rule. Clearing restores inheritance instead. |

Trish used her Sunday-night GLP-1 routine only as an example of a strict recurring restriction. This is not a request to create a medication task or calendar entry, or to advise on medication timing. Exact time bounds remain explicit configuration rather than inferred from the word “night.”

This settles day-scoped fall-through. Normal ranking and optional refinement are settled below; detailed algorithm and effort estimates remain implementation/design work.

### Normal ranking and optional schedule refinement

**Approved normal behavior:** Preserve existing task priority/deadline ordering, using preferences to choose among eligible placements. A preference must not cause an avoidable deadline miss: use an eligible afternoon fallback when preferred evenings cannot meet the deadline. When both placements meet the deadline, favor the preferred window provided doing so does not prevent a higher-ranked task from being placed. Hard requirements and pinned blocks remain protected. Explain unmet preferences when deadlines or competing work determine placement.

Use bounded behavior in the existing scheduler rather than promising a global optimum. Normal scheduling must still produce sensible placements; refinement is not a required repair step after every run. Capture concrete undesirable-placement examples in acceptance rather than leaving “nothing weird” as an untestable criterion.

**Approved optional follow-on slice for this version: “Make it pretty.”** Preserve and assess a separately scoped refinement capability. It may spend additional effort rearranging movable work to improve the user's preferred arrangement. It is not a blocker for S1–S4 completion or core release closure.

**Decision gate:** After normal scheduling passes acceptance, Jim assesses the remaining refinement work and brings Trish a concrete go/no-go recommendation. Preserve the shared API/CLI path and preview/apply contract in the foundations without making core delivery depend on implementing refinement. If deferred at that gate, core delivery may close with refinement explicitly recorded as outstanding. If selected, refinement receives its own implementation slice and quality gate. This does not defer the normal scheduler's approved preference handling or sensible-placement acceptance requirements.

- Expose refinement through shared API/CLI services so Julie, Dex, and Assist can request it; a UI action can use the same capability.
- Use known preferences. Ask a focused question when the desired improvement is unclear, rather than requiring the user to redefine existing preferences.
- Protect hard requirements and pinned blocks. Refinement alone grants no exception authority.
- Preferences may justify more movement, but may not silently worsen commitments. Any proposal that newly misses a deadline or displaces higher-priority work must identify that tradeoff and require explicit approval.
- Preview before applying: show which tasks move, the preference improvements, relevant deadline/placement impacts, and the amount of movement. Preserve normal preview-staleness validation and authorized apply semantics.
- Make a bounded attempt, not a promise of mathematical perfection. Report when no meaningful improvement is found.
- Include Julie in the resulting schedule-change handoff as described below.

Example request: “Julie, I don't like the order of these tasks. Make it pretty.” A proposal might group errands and move coursework into evenings, identify displaced flexible tasks, and state whether deadlines and pinned appointments remain intact. These are illustrative improvements, not implicit new grouping rules.

### General availability for unassigned tasks

- Provide an editable **General availability** policy, independent of Work and Personal. A task with no explicit or inherited assignment uses General; show that it comes from the user's defaults.
- Do not automatically union all Work and Personal hours for unclassified tasks. The user may deliberately configure General to cover those hours.
- For existing accounts, seed General from existing scheduling days/hours while preserving effective eligibility and existing task/map constraints.
- For fresh accounts, start General at **Monday–Friday, 09:00–17:00 in the user's timezone**, visibly editable in Scheduling settings. This is a starting schedule, not an employment classification.
- Keep fallback tasks linked to General rather than copying its hours into each task. Changes affect subsequent scheduling calculations and stale relevant previews through the shared revision contract; saving settings does not automatically move existing blocks.
- If General offers no usable time, explain the failure instead of borrowing another policy's windows.

### Nominal workday conversion

**Approved:** Nominal effort conversion is separate from scheduling availability. Changing working hours or the nominal conversion setting does not change how much work an existing task requires.

- One workday represents a configurable amount of effort; initialize new accounts at eight hours. Existing accounts may seed this distinct setting from their current workday-length value during migration.
- Convert to stored effort minutes when saving. Two workdays at eight hours becomes 960 minutes (16 hours). Later changing the nominal workday to six hours does not rewrite that estimate.
- Show the conversion before saving, for example “2 workdays = 16 hours.” An explicit later estimate edit expressed in workdays uses the then-current conversion, visibly, before save. Unrelated edits must not reconvert the estimate.
- Effort does not imply one continuous block. Placement and splitting follow the task's independent rules.
- Use “workday” for nominal effort and “day” for calendar/date operations. “Tomorrow” advances the local calendar date rather than adding nominal effort hours. Ambiguous effort input such as “2d” requires clarification rather than silent conversion.

Acceptance: verify save-time conversion, unchanged effort after either availability or nominal-setting changes, unchanged effort on unrelated task edits, explicit re-estimation with visible current conversion, and calendar-date versus workday-effort distinctions.

### Duration input and precision

**Approved:** Accept friendly hours/minutes consistently across UI, CLI, and Assist: 90m, 1h 30m, and 1.5h all mean 90 minutes. Accept explicit fractional workdays using the current nominal conversion with visible save-time conversion. A bare number in a field labeled minutes means minutes; conversational input requires clarification when units are unclear. Ambiguous effort shorthand such as 2d requires clarification, not an assumed workday or 48-hour conversion.

- Convert the complete input before rounding once to the nearest whole minute; exact halves round up. Show normalized values when rounding changes them. For example, 1.333h becomes 80 minutes.
- Reject negative durations with useful errors. Correct recorded effort through the correction workflow rather than a negative duration entry.
- If a positive input rounds to zero, request at least one minute instead of silently saving zero. Zero is valid for remaining effort and buffers, not a block-size bound or a new time-worked entry.
- Blank optional bounds inherit defaults, never zero or unlimited. An unlimited maximum remains an explicit choice.
- Preserve effort precision independently of placement granularity. An 80-minute estimate remains 80 minutes even if starts align to a scheduling grid; account for any placement rounding explicitly without rewriting recorded effort.

**Explicitly deferred, still wanted:** week/month effort units are V.Next-Not-Now, not rejected or removed from the future product. Trish expects to need them later. Their future contract must distinguish nominal working effort, elapsed durations, and calendar periods before implementation. For this version, retire silent fixed effort conversions for w/mo, explain supported alternatives, and clarify requests such as “this takes two weeks.” Do not alter previously saved estimates. Calendar-date expressions such as “due in two weeks” remain a separate date-handling concern and are not prohibited by this effort-unit deferral.

Acceptance: equivalent mixed/decimal unit inputs; fractional workdays; visible rounding including half-minute ties and positive values rounding to zero; field versus conversational bare numbers; negative rejection; valid zero remaining/buffer values; blank versus unlimited bounds; ambiguous day/week/month effort clarification; unchanged saved estimates; and separation of effort from placement-grid rounding.

### Task chunking and progress

**Approved for this version:** Deliver task block-size controls and effort-progress tracking through supported shared interfaces, including UI and CLI. Existing database/scheduler block fields alone do not constitute delivery.

**Optional bounds:**

- Omitted minimum or maximum inherits the corresponding user default. Either or both may be omitted. Show the effective value and its source; an explicit task value overrides only that bound.
- Provide an explicit maximum “No limit,” distinct from omission/inheritance. Remaining work and eligible windows still limit placement.
- “Keep in one block” requires all remaining work to fit in one continuous eligible window; it is distinct from an unlimited maximum.
- Validate effective bounds together. If a three-hour explicit minimum conflicts with an inherited two-hour maximum, require correction rather than silently changing either.
- A final remainder may be smaller than the minimum. Eight hours with minimum one hour/maximum three hours may fit as 3+3+2 or 2+2+2+2; a final 30-minute remainder is allowed. Buffers are separate from work duration.

**Track distinct quantities:**

- Original estimate: retain the initial estimate for reference.
- Time worked: explicitly recorded effort, never inferred merely because a scheduled block elapsed.
- Remaining estimate: current estimate of unfinished work; drives future scheduling.

**Low-friction progress:** Enter time worked and show a suggested remaining estimate reduced by that effort, editable before saving. Two hours worked against eight remaining can suggest six remaining, but the user may keep eight remaining if more work was discovered. Allow remaining-only re-estimation without a time entry and task completion without accounting for every minute. Logging effort does not silently mark Done; at zero remaining, offer completion explicitly. A missed calendar session does not reduce remaining work.

Preserve progress history with corrections supported. Duplicate retries must not double-log effort. Progress changes stale affected schedule previews but do not silently rearrange blocks. Prefer a display such as “2h worked · about 6h remaining” over implying that elapsed effort reliably measures percentage completion.

**Pinned reservations:** Future pinned blocks reserve part of remaining work, not completed effort. With six hours remaining and two reserved in a future pin, place four additional hours. Past blocks are not evidence of completion. If pinned reservations exceed remaining effort, surface the mismatch rather than silently trimming or moving pins.

**Acceptance:** independently omitted bounds and inherited-value display; explicit unlimited maximum; contradictory effective bounds; keep-in-one-block behavior; allowed final short remainder; editable remaining suggestion; increased/remaining-only estimates; missed sessions; zero remaining without silent completion; completion without time logging; correction history; duplicate-safe logging; preview invalidation; future versus past pins and excess-reservation conflicts. Define migration of existing tasks and any in-progress block boundary cases in the implementation contract before relying on the new remaining-work calculation.

### Overnight and split windows

**Approved for this version:** Support multiple windows per day and explicit overnight windows.

- Split daily windows, such as Monday 09:00–12:00 and 14:00–17:00, offer alternatives while the intervening gap remains unavailable. This does not authorize splitting a task: separate task splitting rules determine whether its effort can occupy multiple blocks. One continuous block cannot bridge an unavailable gap.
- Overnight windows explicitly identify a next-day end, such as Monday 22:00 to Tuesday 02:00. Expose an “ends next day” choice rather than inferring overnight from end-before-start. Equal start/end must not silently mean either zero duration or 24 hours.
- The start day identifies the recurring window. Every Monday 22:00–02:00 includes early Tuesday. Independent requirements still apply at actual times: a separate Monday-only restriction excludes the Tuesday portion.
- Replacing a Monday overnight occurrence replaces the full occurrence, including its Tuesday tail. Show that scope in the editor and proposal.
- Midnight alone does not require splitting a task block when the entire interval remains eligible. Availability, busy time, context, and task requirements continue to constrain the whole block.
- Define windows in the configured schedule timezone, not browser timezone. Preserve wall-clock window definitions across daylight-saving transitions and count actual elapsed time for task effort.

Acceptance: split-day gap protection with splittable and unsplittable tasks; recurring Monday overnight eligibility; an independent Monday-only restriction; replacement of the Tuesday tail; a continuous block across midnight; and a browser timezone different from the schedule timezone.

### Daylight-saving boundary resolution

**Approved:** Use shared deterministic resolution across scheduler, UI, CLI, and Assist, in the configured schedule timezone.

- For a recurring window whose boundary falls in a nonexistent local-time gap, move that boundary to the first valid instant after the gap. Do not shift the entire window to preserve its normal duration. If the resolved occurrence has no positive duration, skip it with an explanation; do not invent availability.
- For a typical 02:00→03:00 jump: 02:30–04:00 becomes 03:00–04:00; 01:00–02:30 becomes 01:00–03:00 with one elapsed hour; 02:15–02:45 yields no available time. These are fixtures, not an assumption that all timezone transitions are one hour.
- For recurring ambiguous boundaries during a repeated hour, default to the first occurrence consistently for start and end. Support an explicit second-occurrence override. A 01:15–01:45 recurring window occurs once in the first repeated hour, not twice or as an expanded 90-minute window.
- A window spanning the whole backward transition includes the extra elapsed time. This differs from choosing an ambiguous boundary occurrence.
- For an explicitly entered one-time nonexistent boundary, flag it and offer a valid replacement before saving. For a one-time ambiguous boundary, require a first/second occurrence choice and show the timezone offset. Preserve the resolved exact instant.
- Task effort counts elapsed minutes. Recurring wall-clock definitions remain unchanged; adjustments affect the relevant occurrence only. Show adjustments, skipped occurrences, or ambiguity resolutions in preview/explanation.

Acceptance: cover gap and fold boundaries, fully skipped windows, windows spanning transitions, explicit second-occurrence selection, one-time validation, elapsed effort, and agreement across all entry points.

### Overlapping dated availability

**Approved:** Resolve overlaps through explicit operations and visible choices, never save order or an implicit shortest-range-wins rule.

- Additions to the same availability policy combine; overlapping minutes count once.
- Replacements targeting the same policy and dates require explicit resolution of which replaces the other within the overlap.
- For an addition overlapping a replacement, explicitly show whether the extra window survives or is part of what gets replaced. Do not infer this from save order.
- Applicable hard exclusions continue to block allowed windows unless an authorized scoped exception targets them.
- Unrelated policies do not conflict merely because their clock times overlap. Task composition determines which apply.
- Show effective windows before saving. Replacement is limited to its named policy and scope; changing Study does not rewrite Work or General.
- An explicit empty replacement closes the targeted availability without falling through. Expiry or removal restores the underlying applicable arrangement; preview that consequence.
- Reject unresolved conflicts atomically, preserve the draft for correction, and leave saved configuration unchanged.

Acceptance example: replace a week's study evenings with 14:00–16:00, then propose Wednesday 10:00–12:00 instead. Ask explicitly to replace Wednesday's afternoon while leaving the other days unchanged. After approval, Wednesday morning applies. Test additions, addition/replacement choices, exclusions, unrelated policies, empty replacements, restoration, and failed/conflicting applies without partial changes.

### Retirement and deletion of referenced maps and contexts

**Approved:** Retire by default for cleanup; require explicit migration or removal of active uses before deletion.

- Retirement removes an item from normal new-assignment choices while preserving existing assignments and effective behavior. Show its retired status where it remains in use.
- Offer replacement with a compatible item, with a preview of affected assignments/declarations and atomic migration.
- Offer explicit removal of assignments only with a preview of each affected item's inheritance/fallback. Never silently broaden availability through deletion.
- Delete unused items only when no active references remain; preserve understandable historical explanations including the names and effective values used at the time.
- Removing a planned context declaration is distinct from deleting its reusable preset. Deleting Away must not cancel a planned trip or silently restore Home. Removing a declaration explicitly may restore the underlying context, as previewed.
- Check all uses, including defaults, inherited project/epic assignments, future/recurring declarations, and dependent rules. Recheck under concurrency protection on apply so a new reference after preview prevents an outdated deletion.
- Configuration changes stale affected previews but do not automatically move calendar blocks. Schedule changes retain separate preview/apply approval.

Acceptance: retire a referenced map without behavioral changes; atomic replacement and rollback; assignment removal with explicit fallback; referenced preset versus declaration deletion; history after deletion; and a concurrently added reference causing stale/revalidation rejection rather than a dangling reference.

### Editing reusable context presets already in use

**Approved:** Existing declarations retain their approved settings unless explicitly updated. New declarations use the revised preset.

- Offer **Save preset only**, preserving all existing declarations, or **Save and update selected future uses**, previewing affected declarations and committing the preset edit and selected updates atomically.
- Preserve declaration-specific overrides by default. Show “Local override retained” in the preview; replacing one requires an explicit choice.
- Allow a recurring declaration's future occurrences to be updated as a group from an explicit effective date. Preserve past occurrences and their history.
- Leave an occurrence already underway unchanged by default. Offer an explicit separate choice to update the current occurrence too.
- Retain and expose preset revision provenance, including when a declaration uses an earlier revision or local overrides. Intentional differences are valid and do not require correction.
- Context updates invalidate relevant previews without automatically moving calendar blocks. Busy events and explicit scoped corrections retain their approved precedence.

Acceptance example: At theatre previously supplies phone access but no computer; its preset is edited to include computer access. Verify new declarations use the revised preset, existing ones stay unchanged under preset-only save, selected future uses update atomically, a visit explicitly marked no-computer retains its override, recurring updates honor the effective date, and current/past occurrences remain unchanged unless the current occurrence is explicitly selected. Test stale proposals and rollback under the shared apply contract.

### Atomic configuration apply

**Approved:** One approved configuration proposal applies completely or none of its changes take effect. Validate and commit the proposal's application data as one transaction. Any operation failure rolls back the proposal's changes and returns an understandable error; do not leave a partially configured arrangement.

- Check relevant configuration revisions under the shared concurrency protection before committing. If relevant inputs changed since proposal preparation, reject as stale and refresh for review rather than silently applying outdated assumptions.
- A safe retry uses the same idempotency key and submitted intent. If the original apply committed but its response was lost, return its recorded receipt without duplicating effects. Reject reuse of a key with different instructions. Persist the successful result consistently with the committed changes so a connection failure cannot split them.
- Distinguish saved, not saved, and result temporarily unknown after a connection problem. Do not describe an uncertain outcome as a confirmed failure; allow result recovery through the same request identity.
- Keep configuration apply separate from schedule preview/apply. New rules invalidate affected previews but do not move existing blocks merely because configuration was saved. Preview the schedule under the new rules and obtain separate approval to apply it.
- Julie's notification/handoff follows successful configuration save and is not part of the database transaction. If that handoff fails, retain the committed changes and receipt, identify the pending handoff, and retry communication without reapplying configuration. This does not authorize a new messaging integration.

Acceptance: a proposal creates a study map, attaches it to Education, and adds a Monday exception. Test complete success, failure at an intermediate operation with no partial effects, concurrent relevant edits/stale rejection, lost response followed by duplicate-safe retry, mismatched key/intent rejection, and a failed handoff after successful commit. Confirm configuration save does not move schedule blocks.

### Context precedence

**Approved:** Resolve location, usable resources, permitted activities, and busy/free status separately. A resource declaration must not erase occupied time.

Apply the following precedence to the relevant dimensions:

1. **Configured baseline** supplies defaults where nothing more specific applies.
2. **Recurring context** replaces relevant baseline assumptions during its hours.
3. **Dated context** overrides recurring context for its declared period.
4. **Reliable event and travel information** overrides conflicting location assumptions and accounts for occupied time. An ambiguous/generic meeting supplies busy time only, without inventing a location or commute.
5. **Explicit scoped correction** corrects the identified information for its stated scope. Correcting an appointment to virtual/Home does not clear its busy status.

Additional approved rules:

- A place change must resolve its resources rather than accidentally retaining the previous place's resources. Generic Away must not inherit Home's computer access. A Work preset can supply its own resources; a trip can explicitly provide phone access and selected laptop windows.
- Same-level conflicting declarations are surfaced, not resolved by last-write-wins. Offer explicit replacement/correction. Until resolved, do not assume either disputed location satisfies a task's location requirements.
- At expiry, restore the underlying context effective at that time. An appointment ending during a week away restores the trip context, not automatically Home.
- Context suitability does not create scheduling availability or waive task requirements. Explicitly declaring a laptop during a busy meeting does not make that meeting schedulable work time.

Acceptance example: recurring Tuesday work context is superseded by a dated week-away declaration with phone access. A virtual Tuesday meeting preserves Away/phone while marking the interval busy. A scoped 16:00–18:00 laptop declaration makes computer-dependent work contextually suitable only during that interval, subject to availability and other requirements. Verify restoration after each interval, generic versus reliably located events, same-level conflicts, and absence of resource leakage from Home.

### Travel scope (item 9)

Ship explicit event travel allowances and preserve an extension point for a later reusable place-to-place matrix. **Defer matrix implementation/CRUD and standing/default commutes.** Remove wording that implicitly commits S2 to shipping the matrix.

Allow different before/after durations and preserve exact boundaries. Overlapping travel intervals consume their shared time once. With event allowances alone, do not claim to have verified a feasible route between successive appointments. Matrix-specific decisions listed in the original review remain future design concerns.

### Scoped exceptions (item 10)

Resolve authorized exceptions before the eligibility layers, as described above. Make the action explicit: add a permitted window, replace a named rule, or waive a named requirement. Avoid a generic ignore-all-restrictions operation. An exception affects only its stated rule, task/date scope, and duration; expiry or removal restores underlying policy. It does not implicitly clear busy time or unrelated requirements.

### Shared collaborator workflow and Julie's coordination role

The supported workflow belongs to **Trish, Julie, Dex, and Assist**, not exclusively Julie. Julie's installed CLI on supernova remains a concrete acceptance case.

- A request such as “These are for work” starts configuration discovery. Reuse existing availability/maps, ask only for missing information, and present an understandable proposal before applying it.
- Routine maintenance should be delegable. Bring decisions requiring Trish's judgment back as focused choices. Do not assume the in-app model can conduct Julie's nuanced prioritization interviews.
- Authorized collaborators use shared validated services and supported interfaces. Provide a receipt identifying what was created/changed, effective scheduling rules, and unresolved matters.
- Keep Julie explicitly informed about schedule-oriented changes, including new projects with scheduling rules, availability/context edits, and applied replans. The handoff should distinguish configuration changes from actual calendar placement and explain why they were made.
- This is a coordination requirement, not authorization to build or use an automatic messaging integration. Use an explicitly authorized communication path; a clear receipt can support the human handoff in the meantime.

### Bounded Assist role and model evaluation timing

**Keep the current Llama 3.2 model for the build. Evaluate alternative models after the build.** Model selection research is not a discovery or release prerequisite.

Assist's intended role is convenient everyday requests inside thePlan, especially from a phone. Examples include creating a task with a duration, assigning it to coursework with inherited rules, proposing an away interval, and explaining why a task was not scheduled. More involved planning and prioritization can go through Julie or Dex.

These are target workflows for implementation and acceptance, not claims that all are already supported. The model interprets intent, requests missing information, and proposes structured changes. Shared application services resolve inheritance, validate constraints, calculate placement, and apply authorized changes. Preserve the distinction between configuration approval and schedule application.

Keep the model replaceable through configuration. Test Assist during the build and record whether failures arise from missing context, workflow design, or model behavior. Retaining Llama does not waive acceptance requirements: unresolved failures remain visible and require a fix or an explicit scope decision.

After the build, compare Llama against a bounded shortlist using repeated real scenarios, correctness, clarification quality, valid proposals, and response latency. Qwen3.5 9B is an initial candidate, not a selected replacement. No model installation or configuration switch is requested by this handoff.

Evaluation hardware reported by Trish: RTX 3090 FE, 24 GB VRAM, preferably reserving 4–6 GB for other use. Target roughly 18–20 GB or less for inference, measuring actual runtime memory, context overhead, CPU offloading, and cold/warm latency rather than relying on download size. Remote Assist calls still run through thePlan API to the model host; ordinary task management must remain usable if Assist is unavailable.

## Evidence and change boundary

### Buffer consistency: requested verification in this pass

Trish requests explicit verification that the existing inter-block buffer behaves properly around **pinned tasks and external calendar events**, as well as newly scheduled blocks. This is a verification request, not a claim that the current implementation guarantees every boundary.

Source inspection found the Settings control “Buffer between blocks (minutes),” a stored default of 5 minutes, and post-block padding for newly placed blocks. Pinned blocks and external events are loaded into the busy map without that padding. No live setting or runtime behavior was verified in that inspection.

Renee/Jim should establish the intended boundary policy and test:

- Configured 0-, 5-, and 10-minute buffers between automatic blocks, including six tasks scheduled in an afternoon.
- Automatic placement immediately **before and after** a pinned task, and before and after a busy external event. Exercise differing task insertion/priority orders so a later-created block placed earlier in time cannot evade the expected gap.
- Tight gaps, adjacent fixed items, window edges, and deadlines: report insufficient capacity without moving pins, changing external events, or silently dropping a required buffer.
- Whether buffers separate split blocks of one task as well as different tasks; make the actual policy clear in settings/help and acceptance evidence.
- Interaction with explicit event travel allowances: specify whether a transition buffer adds to travel time or is already satisfied by it; do not accidentally double-charge or silently erase required time.
- Preview/apply agreement and invalidation after changing the buffer setting.

Record the agreed semantics, observed results, and any defects. Existing fixed items may already be too close together; distinguish reporting such a conflict from guaranteeing a gap that would require moving them. A global setting exists; afternoon-only or per-selection buffer editing is not newly approved scope.

## V.Next-Not-Now: location-aware errand suggestions

**Captured option only. Deferred beyond this scheduling/settings pass.** No implementation, device access, or automatic scheduling is requested.

**Trish's scenario:** A calendar lunch with Eric and Scott takes her to Redmond. An outstanding task is to visit Trader Joe's for Unexpected Cheddar. The system notices the potential opportunity and asks whether she wants to add the errand to that day.

**Possible first scope: calendar-based awareness.** Use an explicitly identified event destination and a task's associated place or area to propose a relevant nearby errand. Do not infer a precise location from ambiguous event text. Ask before adding or rearranging anything; explain the connection. Discovery would need to address branch selection, travel/detour time, opening hours, available time, task relevance, and avoiding repeated unwanted suggestions. These are future design questions, not a promise of route optimization.

**Possible later scope: device-based awareness.** Opt-in location services on a phone or smartwatch could support suggestions based on actual presence rather than planned calendar destinations. Treat this as separate, more involved scope requiring investigation of platform support, permissions, background behavior, battery use, location accuracy, notification controls, and data retention. Calendar-based suggestions should not require continuous device tracking.

Preserve the human decision: suggest the opportunity, let Trish accept, decline, or defer, and preview any resulting schedule changes. Keep Julie informed when an authorized schedule change is applied. This idea does not activate location tracking or reopen the deferred travel matrix/standing commute scope for the current release.

This update records Trish's product decisions. It does not report new code/model validation or authorize implementation, commits, pushes, live configuration changes, or external messages. Jim and Page should reconcile the working plan/spec with these decisions through the existing gates.
