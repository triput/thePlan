# Adding a Coursera course through the CLI

**Filename:** AGENT-COURSE-IMPORT.md  
**Last modified:** 2026-10-09  
**File version:** 1.0  
**Audience:** Julie and other agents working with Trish

Use this guide to turn a real course syllabus into a reviewed project in thePlan. Capture the supplied curriculum, propose its structure, apply the agreed version, and verify the created records. Keep the source outline, approved proposal, idempotency key, and receipt together for reuse and recovery.

This is also a practical end-to-end CLI test. A successful course import exercises authentication, structured entry, hierarchy creation, defaults, receipts, and readback. It does not by itself validate scheduling, dependencies, updates to existing work, or every CLI command.

The commands below match the local implementation checked on 2026-10-09. Confirm that the target instance has the templates feature deployed. Installation and configuration details are in [the CLI README](../../apps/cli/README.md).

## First use with Trish

The first planned use is Trish's Coursera Kubernetes course. She has **not started it**, so all coursework should enter as uncompleted. Trish will confirm Julie's CLI access and provide the course link. The exact course title and syllabus are not yet supplied.

Propose one standalone course project unless Trish chooses an existing epic. Review optional work, estimates, and scheduling behavior with her before Apply. Do not run Update Schedule as an incidental part of importing the course.

## 1 Confirm the destination and account

Use Trish's intended thePlan instance. `THEPLAN_API_URL` is the base URL, without `/api/v1`. Preserve an existing correct configuration. `THEPLAN_SESSION_FILE` identifies the saved session file; keep its contents private.

```text
theplan version
theplan auth me
theplan templates list
theplan --format json templates get coursera_course
```

Confirm that `auth me` identifies the account whose plan Trish wants updated. If login is needed, use the approved credential flow. The CLI supports `theplan auth login --identifier ACCOUNT --password-stdin`; supply the password through protected standard input, not a saved guide or proposal.

The course detail response includes `example_outline`. It documents the input structure; its sample lessons are not the real curriculum. Confirm that detail retrieval succeeds, not just catalog listing.

## 2 Gather the actual syllabus

Use the course link Trish supplies. Capture its exact title, provider, URL, module order, and available lesson, reading, quiz, assignment, and lab details. If enrollment or login hides the syllabus, ask for access or an export. Do not substitute a plausible curriculum for unavailable source material.

| Course content | thePlan entity |
|---|---|
| Course | One project |
| Module or week | Section |
| Actionable lesson, reading, quiz, or lab | Task |

Preserve optional flags. Do not invent deadlines or dependencies merely because items appear in syllabus order. For a later reuse of this guide, establish current progress first; the all-uncompleted assumption applies to this first course only.

## 3 Build the outline

Create a dedicated working folder for this import. Save UTF-8 JSON as `course-outline.json`. Use `example_outline` as the schema reference and replace all sample content. The illustrative shape below is not actual Kubernetes course content:

```json
{
  "course": {
    "course_order": 1,
    "title": "Exact course title",
    "url": "https://example.com/replace-with-course-url",
    "modules": [
      {
        "module_order": 1,
        "title": "Exact module title",
        "tasks": [
          {
            "id": "m01-t01",
            "task_order": 1,
            "task_type": "video",
            "title": "Exact lesson title",
            "duration_minutes": 12,
            "optional": false
          }
        ]
      }
    ]
  }
}
```

Give tasks distinct IDs. Use published durations where available, distinguishing video runtime from estimated hands-on effort. For unknown durations, omit `duration_minutes` and disclose the settings-derived default returned by Propose. Course/module `estimated_hours` does not distribute scheduling time among tasks.

## 4 Propose and review

```text
theplan --format json templates propose coursera_course --file course-outline.json
```

Save the successful JSON response intact, in UTF-8, as `course-proposal.json`. Check the command's exit status before treating captured output as a usable proposal. Apply accepts this saved response directly.

Without attachment arguments, the course becomes a standalone project. To attach under an agreed existing epic, use its verified UUID:

```text
theplan --format json templates propose coursera_course --file course-outline.json --attach-kind epic --attach-id EPIC_UUID
```

Inspect `summary`, `payload`, `resolved_defaults`, `warnings`, and `is_scaffold`. Show Trish the destination, hierarchy, required/optional counts, supplied and defaulted estimates, scheduling policy, and any unresolved source gaps.

Optional tasks are included by default. Add `--skip-optional` only when that matches her choice. Check existing projects and source warnings before creating another instance: Apply does not merge with an existing course.

Templates currently propose a **manual** scheduling policy. Explain that policy. If Trish wants automatic scheduling, agree on and review the required change separately; do not silently replan her calendar during import. Regenerate the saved proposal after changes to the outline or attachment choices.

## 5 Apply the agreed proposal

After Trish authorizes the reviewed version, generate a UUID and save it as `idempotency-key.txt` **before** sending Apply. Replace `SAVED_UUID` below with that saved value:

```text
theplan --format json templates apply coursera_course --file course-proposal.json --idempotency-key SAVED_UUID
```

Save the successful response as `course-receipt.json`. If the request times out or its outcome is uncertain, look up the receipt:

```text
theplan --format json templates receipt --idempotency-key SAVED_UUID
```

If retry is necessary, use the **same proposal and same key**. Do not generate a new key because a response was lost. If an uncertain apply is followed by a requested content change, establish the original outcome before deciding how to make that change.

## 6 Verify the result

Use the receipt's entity IDs to read back the project and representative tasks:

```text
theplan projects get --id PROJECT_UUID
theplan tasks get --id TASK_UUID
```

Confirm the destination, entity counts, parent relationships, module order, task estimates, uncompleted state, and agreed scheduling behavior. Include an optional task and a default-duration task in the sample when present. Look up the receipt by key and confirm that it identifies the same import.

Report what was created, where it lives, which estimates used defaults, and what remains unresolved. Retain these artifacts together:

| Artifact | Purpose |
|---|---|
| `course-outline.json` | Source-derived curriculum |
| `course-proposal.json` | Exact reviewed proposal used for Apply |
| `idempotency-key.txt` | Stable key for receipt lookup and safe retry |
| `course-receipt.json` | Created entity IDs and import result |
| `verification.md` | Readback results, source gaps, and decisions |

## Reusable handoff template

Copy and fill this brief for the next course:

```text
Course title and link:
Target thePlan instance and account:
Destination: standalone project or existing epic UUID
Current progress:
Syllabus source and any inaccessible content:
Optional work: include or exclude
Duration policy and known missing estimates:
Scheduling policy:
Approved proposal file:
Apply authorization:
Saved idempotency key file:
Receipt file and created project ID:
Verification results and remaining questions:
```

For the CLI test record, distinguish verified results from unchecked paths. A normal successful Apply and receipt lookup do not prove lost-response recovery or concurrent retry handling; those require their own tests.
