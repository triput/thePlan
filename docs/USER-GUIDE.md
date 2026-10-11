# thePlan — User Guide

Practical guide for running and using **thePlan** as a household operator. Covers the stack through **W3+** as shipped today: login and recovery, hierarchy and batch edits, calendar blocks and auto-schedule, Assist, outline import, trash/archive, and settings.

For developer setup, see the root [README](../README.md). For doc inventory and waves, see [docs/README.md](./README.md). Guests on a live instance can skim [guides/QUICK-START.md](./guides/QUICK-START.md) instead of this runbook.

---

## What you get

thePlan is a personal task and calendar app (Todoist + SkedPal style) on your machine or home server:

- **Hierarchy** — Epic → Project → Section → Task → subtask (up to two nesting levels below a top-level task)
- **Smart views** — Inbox, Work, Today, Upcoming, saved views, epic aggregate, projects, labels
- **Board view** — Kanban columns (Ready, In progress, Waiting, Done) on supported views; toggle **List** / **Board** in the list header
- **Batch selection** — Multi-select tasks for priority, due, labels, move, schedule style, delete, or **block as bundle**
- **Calendar** — Day/week grid, due markers, manual blocks, bundles, drag from lists, drag move/resize on desktop, **Update Schedule** auto-placement, Google/Microsoft busy overlay
- **Quick-add** — Natural-language capture (priority, due, duration, project, epic, recurrence)
- **Assist** — Local SLM (Ollama) proposes **create_task** and **create_project**; you review before apply
- **Outline import (Theme F)** — Paste/upload curriculum JSON → epic/project/section/task tree
- **Household login** — Multiple accounts; data isolated per user
- **Recurrence and reminders** — `every` / `every!` patterns; in-app and browser notifications
- **Trash and archive** — Soft-delete tasks; browse and restore; archive epics/projects

**Deep references (not duplicated here):**

| Topic | Doc |
|--------|-----|
| Agent CLI, JSON contract, host recovery commands | [CLI.md](./CLI.md) |
| Assist topology, Ollama, env vars | [SLM-ASSIST.md](./SLM-ASSIST.md) |
| Outline JSON shape and attach-under | [OUTLINE-INGEST.md](./OUTLINE-INGEST.md) |

**Not shipped yet:** filter query language, calendar month view, unified command palette, Assist auto-apply or schedule mutations, voice. See [07-wave-roadmap.md](./07-wave-roadmap.md).

---

## Start the app

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or any OCI-compatible runtime).

From the repo root:

```powershell
docker compose -f infra/compose/compose.yaml up --build
```

| What | URL |
|------|-----|
| **Web app (use this)** | **http://localhost:8080** |
| API (direct; dev/CLI only) | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

**Important:** Open the app at **:8080**, not :8000. The web container proxies `/api` so session cookies stay same-origin. Using :8000 in the browser breaks login.

Stop the stack:

```powershell
docker compose -f infra/compose/compose.yaml down
```

### Backup your data

One-liner (while Compose is running):

```powershell
docker compose -f infra/compose/compose.yaml exec -T postgres pg_dump -U theplan theplan > theplan-backup.sql
```

**Scheduled backups:** from the repo root run `.\scripts\backup-postgres.ps1` (Windows) or `./scripts/backup-postgres.sh` (Linux/macOS). Dumps land in `backups/`; older files prune after 14 days. See the root [README](../README.md) for Task Scheduler / cron examples.

**Remote access:** optional Cloudflare Tunnel — [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md).

---

## Sign in, sign out, and account lock

### First account (setup)

On a fresh database, thePlan shows **Welcome to thePlan**:

1. Choose **username**, **email**, and **password or passphrase** (12+ characters; spaces allowed).
2. Optionally set a **display name** (top bar).
3. Click **Create account**.

The first account claims bootstrap admin and keeps data tied to that user ID.

### Everyday sign-in

Use **username or email** plus password → **Sign in**.

**Sign out:** top-right **Sign out** clears your session.

If the server is unreachable, the login screen offers **Retry**.

### Forced password change

After an admin reset or **host recovery** (below), your account may have **must change password** set. On sign-in you see **Choose a new password** before any other UI. Pick a new 12+ character passphrase → **Update password**, or **Sign out** if you need a different account.

Voluntary password changes: **Settings → Account**.

### Host recovery (CLI)

When email reset is not in scope, an operator with DB access can reset a household password from the host — bumps **session epoch** so old browser sessions stop working. Install steps, env vars, exit codes, and `theplan auth reset-password` flags live in **[CLI.md](./CLI.md)** (not repeated here).

Typical flow: install CLI + API deps → set `DATABASE_URL` → run reset → give the user the temporary password → they sign in and complete **Choose a new password**.

---

## Household accounts (admin)

Each person on this deployment has a **private** task/project/label/calendar space. No shared projects or assignees.

**Settings → Household** (admin only):

| Action | How |
|--------|-----|
| Add a member | **Add user** → username, email, password, optional display name → **Create user** |
| Reset a password | **Set password** on a row → new passphrase → **Save password** (forces change on next login) |
| Disable an account | Uncheck **Active** (not your own session) |

New users sign in at the same URL with their credentials.

### Demo user `nebula`

With `SEED_DEMO_USER=true` (Compose default), a non-admin **nebula** user is seeded with sample data after setup. Credentials are written once to `.secrets-backup/nebula-credentials.txt` (gitignored).

---

## Layout and navigation

The **Workbench shell** (R3 UI refresh) is three regions on desktop: **collapsible sidebar**, **main** (lists, board, or calendar), and an optional **support panel** on the right. Calendar scheduling, preview, and task editing share that panel so the grid keeps width.

```
┌ Sidebar (or icon rail) ┬─ Top bar: Quick-add | Assist | Import | Search | ? | You | Sign out ─┐
│ Views                  ├─ Main: task list, calendar, labels, trash, archived ───────────────┤
│  Inbox / Work / …      │  [Support panel: calendar help, preview, or task details]         │
│  Saved views           │                                                                   │
│  Epics & projects      │                                                                   │
│ Settings (footer)      └───────────────────────────────────────────────────────────────────┘
```

| View | Shows |
|------|--------|
| **Inbox** | Tasks with no project |
| **Work** | Open tasks across projects (smart view) |
| **Today** | Incomplete due today or with a scheduled block today |
| **Upcoming** | Incomplete due or blocked in the next 7 days |
| **Calendar** | Day/week scheduling grid + support panel (desktop) |
| **Labels** | Label CRUD |
| **Archived** | Archived epics and projects (restore here) |
| **Trash** | Soft-deleted tasks (restore or purge) |
| **By label** | Sidebar links when labels exist |
| **Saved view** | Sidebar entries you create; filters and list/board mode persist |
| **Epic / project** | Filtered task lists; epic view groups by project |

### Collapsible sidebar (desktop)

On wide screens, use **`⟨` / `⟩`** beside the brand to **collapse navigation** to a narrow icon rail (flyouts still expose long titles). Your choice is remembered in this browser. On phones and narrow widths, use **☰** for the drawer instead; the rail collapse control is hidden.

### Support panel (right)

The **support panel** sits beside the main content on desktop:

| Context | Panel shows |
|---------|-------------|
| **Calendar**, nothing selected | **Calendar support** — schedule hints, **Preview changes**, unscheduled tasks, **Map & blocks** legend |
| **Calendar**, preview running or ready | **Preview schedule changes** — same proposal flow as before (**Refresh preview**, **Apply whole proposal**) |
| **Any view**, task selected | **Task details** — full edit form; on Calendar, **Collapse** returns to calendar support |

When the panel is collapsed on Calendar, a **Support** tab on the edge reopens it. On narrow screens the panel is a full-height sheet (calendar stays **Day** mode; drag scheduling may be disabled — use the block modal).

**Phone:** ☰ drawer nav; task/support UI is full-screen until closed.

---

## Hierarchy — epics, projects, sections

| Level | Operator notes |
|-------|------------------|
| **Epic** | Sidebar group; **+** adds a project under it. **✎** edit color/title/**archive**. **Demote to project** merges epic down (confirm). |
| **Project** | Task list + optional **sections** bar. **✎** edit, reorder, archive. **Promote to epic** from project edit. Default **schedule style** can be standalone, manual, or bundle. |
| **Section** | Subdivide a project; tasks keep section when moved within project. |
| **Task / subtask** | Detail panel sets parent, project, section. **Promote to project** turns a task subtree into a new project. |

Archive hides epics/projects from normal lists; open **Archived** to **Unarchive**. Deleting a project/epic has confirm dialogs — read them.

---

## Tasks — create, edit, complete, delete

### Quick-add

Top-bar input from anywhere:

1. Type title + optional tokens ([Quick-add tokens](#quick-add-tokens)).
2. **Enter**.

**Q** or **Ctrl+K** (Cmd+K on Mac) focuses quick-add.

On a **project** view, new tasks default to that project unless tokens override. **Inbox** keeps tasks unassigned unless you tag `#Project`.

Parsed metadata shows as chips after submit.

### Task detail panel

Select a task to open **Task details** in the support panel (desktop) or full-screen sheet (narrow):

- Title, description, priority (P1–P4), due, duration
- Project, section, parent (subtasks)
- Labels, recurrence, reminders
- Scheduling: plan, soft target, deadline, schedule style, status (including **overbooked** — see [Scheduler vs calendar conflicts](#scheduler-vs-calendar-conflicts))
- **Save** applies; **Delete task** sends the task to **Trash** (soft delete)

### Unsaved changes

If you edit fields and navigate away (another task, another view, **Collapse** on the support panel, or **Preview changes** while task details are open), thePlan prompts with context-specific actions such as **Save and open**, **Save and switch**, **Save and collapse**, or **Discard**. A failed **Save** keeps your draft and stays on the current task; closing the dialog cancels the navigation.

### Complete and subtasks

- Checkbox, or focus + **X** / **Space**.
- Parent with open subtasks → **Complete parent only** or **Complete all children too**.
- **Recurring:** completing advances **due** to the next occurrence until the series ends or you clear recurrence.

**Show completed** in the list header toggles visibility (saved in this browser).

### Undo

**Ctrl+Z** (Cmd+Z) reverses recent destructive actions in-session (complete, delete, etc.). Delete undo recreates tasks with **new IDs** — not a true undelete from Trash.

### Trash

**Delete task** sends the subtree to **Trash** (soft delete). Open **Trash** in the sidebar to **Restore** (same task IDs) or **Empty trash** / **Purge older than…** for permanent removal.

- Restore a **child** while its parent is still in Trash → the child moves to the **nearest live parent** or **Inbox** (root).
- After you empty trash, purged items cannot be restored; other live tasks (including children you restored earlier) stay put.

---

## Multi-select and batch actions

In task lists (not Trash/Archived):

1. Use the row **select** checkbox, or **Alt+click** select to include visible subtasks, or the **⊞** control on parents.
2. Header checkbox selects all visible rows.
3. The **batch bar** appears above the list.

| Batch action | Effect |
|--------------|--------|
| **Schedule style** | Set **Manual** or **Standalone** on selection |
| **Priority** | P1–P4 |
| **Apply label** | Adds label to each selected task |
| **Due date** | Set date; **Clear due** removes due |
| **Move to project** | Project or **Inbox** |
| **Block as bundle** | Pick **start** (datetime, snaps to 15 min) and optional **Pin** → one calendar bundle for the selection (or parent subtree rules apply) |
| **Delete** | Soft-delete to Trash |
| **Clear** | Clear selection |

Batch operations run against selected IDs; wait for the bar to finish before navigating away.

---

## Quick-add tokens

Leftover text becomes the title.

| Token type | Examples |
|------------|----------|
| Priority | `p1`, `P2`, `!3` (default P4) |
| Duration | `45m`, `1.5h`, `2d`, `1w`, `2mo` — `m` = minutes |
| Due | `today`, `tomorrow`, `next monday`, `2026-08-15`, `at 3pm`, `at 14:30` |
| Epic | `!!Organon`, `!!"Q3 Infrastructure"`, `epic:Auth` |
| Project / section | `#Dev`, `#"Client App"`, `#Dev/Backend` |
| Recurrence | `every monday, wednesday`, `every! 2 weeks from next week until end of year` |

Example:

```text
Review spec 1.5h p1 next Tue at 9am !!Organon #Dev/Backend
```

- **`every`** — next due from completion time (flexible).
- **`every!`** — fixed calendar series (strict).

Label tokens in quick-add are not shipped; use task detail or Labels.

---

## Labels

**Labels** in the sidebar:

| Task | Steps |
|------|--------|
| Create one | Name (lowercase) + color → **Create label** |
| Create many | One name per line, shared color |
| Edit / delete | **✎** → rename, recolor, delete |

Deleting a label can reassign tasks to other labels you check first.

Toggle labels on tasks in the detail panel; **By label** filters lists.

---

## Calendar

Open **Calendar**. **Day** / **Week**, prev/next/**Today**. Titles include day-of-year and ISO week numbers. On desktop, the **Calendar support** panel summarizes schedule state, links a few unscheduled tasks, and documents block/Time Map legend (**Preferred**, **Acceptable**, **Excluded**, external busy, pinned vs movable).

### Due markers and blocks

- **Due markers** — colored ticks for tasks with due date/time.
- **Scheduled blocks** — time you (or **Update Schedule**) placed on the grid.

**Create a block:**

1. **Click an empty slot** → modal with start/end.
2. Choose task, times, optional **Pinned** (replan skips pinned blocks).
3. **Save**.

**Edit/remove:** click block or marker → modal → change or delete.

**Bundles:** multi-task blocks from batch **Block as bundle** or bundle schedule style. Opening a bundle block can **Release remainder** when a task completed early — frees unused time for replan.

**Clear unpinned** (toolbar) removes unpinned blocks in the visible day or week (confirm). Pinned blocks stay.

### Time Map overlay (three tiers)

Toolbar **Time Map** chooses a map or **Neutral** (no band tint). When a map is selected, the grid draws **quieter** green / yellow / red bands:

| Tier | Meaning |
|------|---------|
| **Preferred** (green) | Best windows for auto-schedule |
| **Acceptable** (yellow) | Allowed with lower preference |
| **Excluded** (red) | Forbidden; wins when bands stack |

External **busy** blocks stay gray and ignore the overlay. Day/week bounds, overrides, and settings timezone behave as before — only the visual density changed in the Workbench refresh.

### Preview changes vs Update Schedule

These stay **different** operations:

| Control | What it does |
|---------|----------------|
| **Preview changes** (toolbar or calendar support) | Calculates a proposal and stores it **without** changing live blocks. Review in **Preview schedule changes** (support panel on desktop). **Apply whole proposal** commits the shown proposal; **Refresh preview** / **Generate fresh preview** when stale. |
| **Update Schedule** | Runs collect → calculate → **apply** in one flow (direct replan). |

Opening a preview does not move committed placements. Editing tasks can invalidate an open preview; apply still enforces server checks (stale, expired, conflicts).

### Drag and drop

| Gesture | Where |
|---------|--------|
| **⠿ handle** on a task row | Drag onto calendar grid → creates a block at drop time (uses task duration) |
| **Block / due marker** | Drag to move; drag edges to resize (desktop day/week; narrow screens may prefer the modal) |

### Update Schedule

Toolbar **Update Schedule** runs the fuzzy planner and **applies** results: places eligible tasks into open time using Time Maps, workday settings, dependencies, and task metadata. **Manual**, **bundle**, and pinned blocks are respected per rules in Settings and task schedule style. Use **Preview changes** first when you want to inspect diffs without touching live blocks.

When replan finishes, a toast summarizes moves and any **overbooked** count.

**Docker Compose (default stack):** a separate **`scheduler`** container polls and runs replan after the API accepts the run. **Tauri desktop / bare API-only uvicorn** does not include that poller unless you start one or enable the in-process thread bridge — if **Update Schedule** spins at “running” for a long time, use full Compose (`scheduler` service) or see [DESKTOP.md](./DESKTOP.md) / [apps/api/app/scheduler/README.md](../apps/api/app/scheduler/README.md).

### Scheduler vs calendar conflicts

Two different signals — do not conflate them:

| Signal | Meaning | Where |
|--------|---------|--------|
| **Overbooked** badge | Planner could not fit remaining work before a **deadline** | Task list row; filter **Overbooked only** in list header; task detail scheduling note |
| **Schedule conflict** banner | Two or more **blocks/busy events overlap** in the visible range | Calendar toolbar count; conflicting items highlighted on the grid |

Fix overbooking by extending deadline, reducing duration, clearing blocks, or running **Update Schedule** again after changes. Fix overlaps by moving/resizing blocks or clearing one side.

External **busy** time from linked Google or Microsoft calendars appears as read-only busy blocks (configure under **Settings → Calendar accounts**). See [MICROSOFT-CALENDAR.md](./MICROSOFT-CALENDAR.md) for Entra setup.

---

## Recurrence

In quick-add or **Task details → Recurrence**:

| Field | Purpose |
|-------|---------|
| **Pattern** | e.g. `every monday, wednesday` or `every! 2 weeks` |
| **From / Until** | Optional date frame |

**Save recurrence** / **Clear**.

On complete: **`every`** slides from completion; **`every!`** follows fixed dates. Clear recurrence to finish early.

---

## Reminders

**Task details → Reminders:**

1. **When** (date/time).
2. **Channel:** in-app toast and/or browser notification (allow permission when prompted).

While signed in, the app polls about every **30 seconds** (and on tab focus). **Remove** clears upcoming rows. Reminders for **trashed** tasks do not fire.

Location/mobile push not shipped.

---

## Assist and Outline import

### Assist

Top bar **Assist** → describe work in plain language → **Propose** → edit/remove rows → **Approve**.

- Supported actions today: **create task**, **create project** (optional epic, color).
- Always human confirm; never silent apply.
- Ollama down → Assist errors softly; normal CRUD still works.
- “Schedule at …” in Assist means task **due**, not a calendar block.

Reachability: **Settings → Assist**. Full setup: [SLM-ASSIST.md](./SLM-ASSIST.md). Agents use [CLI.md](./CLI.md) (`assist propose` / `assist apply`).

### Outline (Theme F)

Top bar **Outline** (beside Assist) → choose template → paste or upload JSON → propose → review → approve. Builds epic → projects → sections → tasks. Details: [OUTLINE-INGEST.md](./OUTLINE-INGEST.md).

---

## Search

**/** or the search box — matches title and description; pick a row to open detail.

---

## Settings (highlights)

**Settings** (sidebar gear):

| Section | Purpose |
|---------|---------|
| **Account** | Display name, email, password (all users) |
| **Theme / custom colors** | Presets + optional hex overrides (browser localStorage). Default **Dark** is the cool Workbench look; **Midnight** is a separate **light** navy preset (not the dark Workbench theme) |
| **Scheduling defaults** | Timezone, locale, workday/workweek, default duration, default schedule style, focus windows hook |
| **Calendar display** | 24h vs 6–22, overlay preferences |
| **Time Maps** | When you may be scheduled (tiers for Update Schedule) |
| **Plans** | Named soft frames with optional soft targets |
| **Calendar accounts** | Google / Microsoft connect for busy overlay |
| **Assist** | Status / reachability |
| **Household** | Admin user management |

Save scheduling defaults explicitly when the form shows **Save** (dirty state).

---

## Trash and Archived

### Trash

**Sidebar → Trash** lists soft-deleted tasks with deleted timestamp.

| Action | Effect |
|--------|--------|
| **Restore** | Returns task to normal lists |
| **Empty trash** | Hard-delete everything in trash (confirm) |
| **Purge older than N days** | Hard-delete only items older than threshold |

No background auto-purge — clean up manually. Subtasks deleted with a parent appear in trash together.

### Archived

**Sidebar → Archived** lists archived epics and projects. **Unarchive** returns them to the sidebar. Tasks in archived projects stay in the database; unarchive to work them normally.

---

## Keyboard shortcuts

Press **?** (outside text fields) for the overlay. On **Windows**, the help dialog shows **Ctrl+K** and **Ctrl+Z** (on Mac it shows ⌘). Shortcuts are suppressed while you type in a field or a modal is open.

| Keys | Action |
|------|--------|
| **Q** or **Ctrl+K** (⌘K on Mac) | Focus quick-add |
| **/** | Focus search |
| **Ctrl+Z** (⌘Z on Mac) | Undo |
| **J** / **K** or **↑** / **↓** | Move focus in lists |
| **Enter** | Open focused task |
| **X** or **Space** | Complete / uncomplete focused task |
| **?** | Shortcuts help |
| **Esc** | Close modals and panels |

---

## Tips for daily use

1. Bookmark **http://localhost:8080** (or your tunnel URL) on each device — not :8000.
2. **Today** = due today plus blocks overlapping today.
3. Capture in **Inbox**; batch-move to projects when ready.
4. Use **Update Schedule** after changing Time Maps, deadlines, or clearing unpinned blocks.
5. Watch **Overbooked** in lists vs **conflicts** on Calendar — different problems.
6. Back up before upgrades (`backup-postgres` script or pg_dump).
7. Remote tunnel ops: [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md).

---

## Related docs

| Doc | Contents |
|-----|----------|
| [README.md](../README.md) | Compose, dev setup, backup |
| [CLI.md](./CLI.md) | Agent CLI and host recovery |
| [SLM-ASSIST.md](./SLM-ASSIST.md) | Assist / Ollama |
| [OUTLINE-INGEST.md](./OUTLINE-INGEST.md) | Theme F outlines |
| [guides/QUICK-START.md](./guides/QUICK-START.md) | Guest UI tour |
| [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md) | Remote access |
| [MICROSOFT-CALENDAR.md](./MICROSOFT-CALENDAR.md) | Microsoft calendar OAuth |
| [02-functional-spec.md](./02-functional-spec.md) | Full behavior spec |
| [07-wave-roadmap.md](./07-wave-roadmap.md) | Roadmap |
| [CHANGELOG.md](../CHANGELOG.md) | Release notes |
