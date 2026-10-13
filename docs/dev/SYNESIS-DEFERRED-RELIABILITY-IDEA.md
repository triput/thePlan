<!--
==============================================================================
  File: docs/dev/SYNESIS-DEFERRED-RELIABILITY-IDEA.md
  Description: Local reference copy of Squirrel Board idea IDEA-030.
  Component: Planning
  Version: 1.1
  Created: 2026-10-11
  Last Update: 2026-10-11
==============================================================================
-->

# Synesis reliability investigation and optional remote execution

Capture only. Trish explicitly deferred starting this work. This reference copy is stored in thePlan's workspace; it concerns Synesis, not thePlan. Captured and directly verified on private Squirrel Board as IDEA-030 on 2026-10-11: status Captured, nextAction null. The board is the authoritative idea record.

## Why it matters

Synesis is functional, but unpredictable response times and operations that sometimes require retries cause Trish to reach for other programs. The concern is latency predictability and operational reliability, not a reported problem with result quality.

## Recommendation retained

Treat this as a reliability investigation with latency as a symptom. Diagnose representative operations before changing architecture. Local-only execution is open for reconsideration: an optional remote path could help, but local ownership and user control remain priorities. Local-inclusive is an option to assess, not a migration decision already made.

## Ready-to-use Opus brief

Synesis is functional, but unpredictable response times and operations that require retries make me reach for other programs. Trace representative operations end to end and identify where they stall or fail. Examine timeouts, queues, resource contention, model loading, cancellation, and error handling as possible causes, not assumed diagnoses.

Measure repeated runs, including cold and warm starts. Distinguish slow completion, explicit failure, and cases where the UI stops waiting while work continues. Check whether retrying can duplicate work or leave inconsistent state.

Recommend local fixes where the evidence supports them, then assess whether optional remote execution would materially improve reliability or latency. Local-only is open for reconsideration; local ownership and user control remain priorities. Identify what data would leave the device and how that choice is controlled. Produce findings and a proposed implementation sequence before changing the architecture.

The desired outcome: start an operation, trust that it will finish or clearly explain its failure, and retry safely when necessary. Progress indication, cancellation, and useful partial results may help the experience, but must not substitute for fixing stalls and failures.

## Capture boundary

Keep inactive with no assigned next action. Trish subsequently requested a Monday-morning board review for potential promotions and stale ideas. That review does not authorize starting this investigation or promoting this idea automatically.
