<!--
==============================================================================
  File: docs/guides/COLLABORATIVE-PLANNING-WORKFLOW.md
  Description: Baseline human-led, agent-assisted planning and handoff workflow.
  Component: Engineering / Planning
  Version: 1.0 (Approved baseline)
  Created: 2026-10-12
  Last Update: 2026-10-12
==============================================================================
-->

# Collaborative planning: workflow of record

**Status:** Trish approved this as the baseline workflow on 2026-10-12. It is a working default, open to explicit refinement and experiments, not a rigid methodology. This document records process, not authorization to implement or release a particular project.

## Purpose

Reach concrete, reviewable product decisions without making Trish maintain a giant specification in her head or repeatedly copy decisions between collaborators. Ground behavior in real scenarios, capture each approved decision before moving on, and give the implementation team room to solve engineering details.

## Responsibilities

| Role | Responsibility |
| --- | --- |
| Trish | Supplies goals and lived examples, chooses product behavior and tradeoffs, approves scope, and retains final authority. |
| Dex | Proposes concrete behavior, pressure-tests assumptions and edge cases, distinguishes proposals from approvals, maintains the decision handoff, and independently reviews reconciliation and delivered behavior. |
| Jim and implementation crew | Discover existing behavior, propose engineering contracts and migrations, estimate and implement approved slices, and escalate genuine behavioral tradeoffs. |
| Page | Reconciles approved decisions into the authoritative spec, plan, indexes, and traceability records without changing their meaning. |
| Renee / Quality | Maps decisions to meaningful acceptance cases, records evidence and gaps, and keeps automated, browser, installed-CLI, and human validation distinct. |
| Julie and other intended collaborators | Exercise real supported workflows and provide practical feedback. Keep Julie explicitly informed of schedule-oriented changes through an authorized handoff. |

People or agents may cover different roles in a future effort. Roles describe responsibilities, not exclusive capabilities or permission to send external messages.

## Baseline loop

1. **Orient.** Read the current working plan and relevant implementation evidence. Identify the actual decision, existing constraints, and what is unknown. Distinguish code evidence from live or tested behavior.
2. **Walk one coherent decision at a time.** Use a concrete scenario and expected outcome, propose a recommendation, and explain material alternatives. Avoid turning a conversation into a questionnaire of every possible setting.
3. **Pressure-test.** Examine exceptions, conflicts, inheritance, defaults, failure behavior, and the effects on existing users where relevant. A user example illustrates a requirement; it is not automatically a universal default or a request for a live change.
4. **Get a clear decision.** Trish's approval settles the behavior. Keep unresolved details visible; do not label an assistant recommendation approved until it is. Respect later explicit changes of direction.
5. **Capture immediately.** Update the named handoff with the decision, rationale/examples, acceptance expectations, and scope. Maintain filename/version/date headers, verify the saved change, and provide one reusable link. Avoid making Trish relay long passages.
6. **Track scope honestly.** Separate required delivery, optional slices with explicit decision gates, and deferred ideas. Capture useful tangents without silently activating them. Maintain a short trail marker for the decision to resume.
7. **Reconcile before implementation.** Page updates the spec, plan, defect/backlog references, and documentation index. The spec is the approved behavioral contract; the handoff preserves the decision trail; the plan describes execution and gates. Identify explicit supersession rather than allowing conflicting versions to coexist as equally current instructions.
8. **Independently check the reconciliation.** Verify that approved behavior survived, optional work did not become mandatory, deferred work did not disappear or become active, and acceptance covers the new scope. Report narrow corrections rather than reopening settled choices.
9. **Hand off engineering preparation.** Jim and the crew resolve schemas, APIs, migrations, implementation slices, and project-specific entry gates. Bring back concrete choices that change approved behavior or cannot satisfy it; do not require Trish to approve every engineering detail.
10. **Build and verify.** Review the integrated result against the contract. A reported green suite is evidence of that suite, not a substitute for independent acceptance. Keep untested items open with notes; close only on appropriate evidence and required sign-off.

## Minimum handoff content

- Goal, approved behavior, and explicit non-goals.
- Concrete examples, edge cases, and acceptance expectations.
- Clear status: proposed, approved, implemented, verified, or deferred; do not conflate them.
- Required versus optional work, deferred work still wanted, and the owner/timing of later decisions.
- Compatibility, migration, and failure/retry implications where relevant.
- Remaining decisions and engineering gates, with responsible roles.
- Links to the current spec and working plan, and a dated version header.

## Boundaries and flexibility

Product approval is distinct from implementation, deployment, external messaging, and live-data authorization. Follow the actual authorization and gates for the project; do not add redundant approval rituals where work is already authorized.

The aim is less administrative work for Trish. Collaborators maintain the record and report only what was verified. Preserve unrelated changes and avoid unauthorized commits or pushes. Project-specific hygiene or release rules belong in that project's plan; the scheduling pass's particular gates are not automatically universal rules.

Experiments are welcome. State what is changing, why, and what would demonstrate improvement; retain a trail back to the baseline. Refine this document when Trish adopts a change. Exploratory discussion alone does not supersede the workflow.

## Reference example

This baseline emerged from the [Scheduling / Settings decision handoff](../redesign/SCHEDULING-SETTINGS-DEX-DISCOVERY-REVIEW-2026-10-12.md) and its reconciliation into the [approved specification](../SCHEDULING-SETTINGS-SPEC.md). Their domain decisions are examples, not requirements for unrelated projects.
