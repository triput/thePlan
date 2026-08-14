# Defects log

Open product defects that are not wave exit blockers. Priority here is **product severity** (P1–P4), not task priority enum.

---

## DEF-001 — Subtasks added out of sequence appear at list bottom

| Field | Value |
|-------|--------|
| **Severity** | **P2** (mental tax / hierarchy trust; not data loss) |
| **Status** | Open |
| **Found** | 2026-08-10 |
| **Surface** | Project / Inbox task lists (`TaskList`) |
| **Wave** | Deferred to **bug bash** (not W2a); fix when convenient |

### Symptom

Parenting is correct in the data model (`parent_task_id` / `nesting_level`), but the **visual list order** follows global create order (`sort_order`, then `created_at`), not tree order under the parent.

Repro:

1. Create task A with subtasks A1, A2.
2. Create task B with several children (and optionally a nested child).
3. Return to A (or A2) and use **+** to add another child / grandchild.
4. New row is indented correctly but renders at the **bottom** of the list (after B’s branch), not under A.

Screenshot evidence: out-of-order children named like “Spec 2 b.1” / “Spec 2 b.2” appear under later top-level tasks while still indented as if under Spec 2 b.

### Root cause (likely)

`GET /tasks` and the list UI treat the project as a **flat** sequence ordered by `Task.sort_order, Task.created_at`. New tasks often share default `sort_order` (0), so **`created_at` wins** → entry order. Indent uses `nesting_level` only; there is no DFS / “parent then children” layout pass in `TaskList`.

Reorder controls can assign distinct `sort_order` values, which is why in-order entry *looks* fine until you insert under an earlier parent.

### Expected

List shows a depth-first tree: each parent’s children (by sibling `sort_order`) immediately under that parent, regardless of when those children were created.

### Fix direction

1. **Client (sufficient for display):** Before render, order `tasks` as a forest DFS keyed by `parent_task_id`, siblings by `sort_order` then `created_at`/`id`.
2. **Optional API:** On create under a parent, assign `sort_order` among siblings (e.g. max sibling + gap) so flat sort stays coherent for exports/other clients.

### Out of scope for this defect

- Drag-and-drop reparent
- Section-grouped project layout polish
- Soft-delete

---

## DEF-002 — Timezone setting is free-text, not a picker

| Field | Value |
|-------|--------|
| **Severity** | **P4** (UX polish; IANA text works) |
| **Status** | Open |
| **Found** | 2026-08-11 |
| **Surface** | Settings → Scheduling defaults → Timezone |
| **Wave** | Bug bash / polish bundle — non-urgent |

### Symptom

Timezone is a free-text field. Easy to typo; no discoverability of valid IANA zones.

### Expected

Dropdown (searchable preferred) of common/valid IANA timezones; still store the same string on `user_settings.timezone`.

### Notes

Bundle with other small Settings/UI fixes when convenient. Not a Settings expansion exit blocker.

---

## DEF-003 — Mobile task detail: content below deadline clipped, no scroll

| Field | Value |
|-------|--------|
| **Severity** | **P2** (detail unusable on phone for long tasks) |
| **Status** | Open |
| **Found** | 2026-08-14 |
| **Surface** | Task detail sheet / panel on narrow (mobile) viewport |
| **Wave** | Bug bash / cleanup — do **not** derail W3 |

### Symptom

On mobile web, opening a task’s detail view shows content through **deadline**, but nothing below is reachable — cannot scroll the detail body.

### Expected

Detail sheet scrolls so fields below deadline (notes, Time Map, Plan, reminders, etc.) are reachable.

### Notes

Likely overflow / flex / `100dvh` sheet layout; check W1.6 detail-sheet CSS vs nested scroll containers.

---

## DEF-004 — Inbox up/down reorder arrows do nothing

| Field | Value |
|-------|--------|
| **Severity** | **P3** (controls present but inert; workarounds exist) |
| **Status** | Open |
| **Found** | 2026-08-14 |
| **Surface** | Inbox task list reorder arrows |
| **Wave** | Bug bash / cleanup — do **not** derail W3 |

### Symptom

Up/down move arrows in the **Inbox** view do not change task order (no visible reorder; likely no successful `sort_order` swap).

### Expected

Arrows swap sibling/`sort_order` with adjacent visible rows (same behavior as other list views that reorder correctly), or arrows are hidden if Inbox intentionally has no reorder.

## DEF-005 — Mobile layout: word-tower / crushed flex columns (Inbox + Settings)

| Field | Value |
|-------|--------|
| **Severity** | **P2** (Inbox + Settings unreadable on phone) |
| **Status** | Fixed 2026-08-14 |
| **Found** | 2026-08-14 |
| **Surface** | Narrow viewport — task rows, Settings Google Calendar / subscriptions |
| **Wave** | Hotfix (not W3 derail) |

### Symptom

On mobile Chrome, task titles and Settings calendar copy wrapped one word per line; subscription “Primary” controls overlapped checkboxes.

### Root cause

W1.6 touch-target rule applied `min-width/min-height: 2.75rem` to **all** `.icon-btn`, so reorder/subtask buttons stole horizontal space from `.task-title`. Calendar account rows used `flex: 1; min-width: 0` beside Sync/Disconnect, so the info column shrunk instead of wrapping.

### Fix

Scope large touch targets to chrome (header/nav); keep smaller targets on task-row icons; stack calendar account rows and wrap subscription Primary under the label on narrow viewports.
