# thePlan — User Guide

Practical guide for running and using **thePlan** as a household operator. Covers Wave 1 (MVP) plus Wave 1.5 features that are shipped today: login, household accounts, recurrence, and time-based reminders.

For developers and operators setting up the stack, see the root [README](../README.md). For product scope and roadmap, see [docs/README.md](./README.md).

---

## What you get

thePlan is a personal task and calendar app (Todoist + SkedPal style) that runs on your machine or home server:

- **Hierarchy** — Epic → Project → Section → Task → subtask → nested subtask
- **Smart views** — Inbox, Today, Upcoming, projects, labels
- **Calendar** — Day and week views with due markers and manual time blocks
- **Quick-add** — Natural-language capture with priority, due, duration, project tags, and recurrence
- **Labels** — Standalone label management and per-task tagging
- **Household login** — Multiple personal accounts on one deployment; each person’s data is isolated
- **Recurrence** — `every` / `every!` patterns with optional date frames
- **Reminders** — In-app toasts and optional browser notifications

Not shipped yet (do not expect these in the UI): auto-scheduler, Google Calendar sync, filter query language, Kanban board. See [07-wave-roadmap.md](./07-wave-roadmap.md).

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
| API (direct; dev tools only) | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

**Important:** Open the app at **:8080**, not :8000. The web container proxies `/api` to the API so session cookies stay same-origin. Using :8000 directly breaks login in the browser.

Stop the stack:

```powershell
docker compose -f infra/compose/compose.yaml down
```

### Backup your data

One-liner (while Compose is running):

```powershell
docker compose -f infra/compose/compose.yaml exec -T postgres pg_dump -U theplan theplan > theplan-backup.sql
```

**Scheduled backups:** from the repo root run `.\scripts\backup-postgres.ps1` (Windows) or `./scripts/backup-postgres.sh` (Linux/macOS). Dumps land in `backups/` and older files are pruned after 14 days. See the root [README](../README.md) for Task Scheduler / cron examples.

**Remote access:** optional Cloudflare Tunnel — [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md).

---

## First sign-in (setup)

On a fresh database, thePlan shows **Welcome to thePlan** — create the first household account:

1. Choose **username**, **email**, and a **password or passphrase** (12+ characters; spaces allowed).
2. Optionally set a **display name** (shown in the top bar).
3. Click **Create account**.

The first account **claims** the bootstrap admin row and keeps any existing data tied to that user ID. It is automatically an **admin**.

On later visits you see **Sign in** instead. Use **username or email** plus your password.

---

## Sign in and sign out

**Sign in:** Enter username or email and password, then **Sign in**.

**Sign out:** Click **Sign out** in the top-right bar (next to your display name or username). You return to the login screen; your session cookie is cleared.

If the server is unreachable, the login screen shows a retry button.

---

## Household accounts (admin)

Each person who uses this thePlan instance gets their own account. Tasks, projects, labels, and calendar data are **private to that account** — there is no shared-project or assignee model.

**Admin-only:** Open **Settings** (gear icon, bottom of sidebar) → **Household** section.

| Action | How |
|--------|-----|
| Add a member | **Add user** → fill username, email, password, optional display name → **Create user** |
| Reset a password | **Set password** on any row → enter new passphrase → **Save password** |
| Disable an account | Uncheck **Active** (you cannot disable your own account while signed in) |

New users sign in at the same URL with their own credentials.

### Demo account `nebula`

When `SEED_DEMO_USER=true` (default in Compose), a non-admin demo user **nebula** is created after setup completes, with sample epics, projects, and tasks. Credentials are written once to `.secrets-backup/nebula-credentials.txt` (gitignored). Use it to explore without touching your admin data.

---

## Layout and navigation

```
┌ Sidebar ──────────────┬─ Top bar: Quick-add | Search | ? | You | Sign out ─┐
│ Views                 ├─ Main: task list, calendar, or labels ─────────────┤
│  Inbox / Today / …    │                                                  │
│  Labels               │  [Task detail panel when a task is selected]      │
│  Epics & projects     │                                                  │
│ Settings (footer)     └──────────────────────────────────────────────────┘
```

**Sidebar — Views**

| View | Shows |
|------|--------|
| **Inbox** | Tasks with no project |
| **Today** | Incomplete tasks due today or with a scheduled block today |
| **Upcoming** | Incomplete tasks due or blocked in the next 7 days |
| **Calendar** | Day/week grid (see below) |
| **Labels** | Label management screen |
| **By label** | Quick links to label-filtered lists (when labels exist) |

**Sidebar — Structure**

- **Epics** — Expand/collapse; projects live under epics. Use **+** on an epic to add a project.
- **Projects** — Standalone projects (no epic) and epic children. Click to open the project task list. **✎** edits title/color/archive; reorder arrows change sort order.

---

## Tasks — create, edit, complete

### Quick-add (fastest)

The top-bar input captures tasks from anywhere:

1. Type a title plus optional tokens (see [Quick-add tokens](#quick-add-tokens)).
2. Press **Enter**.

Shortcuts: **Q** or **Ctrl+K** (Cmd+K on Mac) focuses quick-add.

If you are on a **project** view, new tasks default to that project unless tokens say otherwise. On **Inbox**, tasks stay in the Inbox unless you tag a project.

Parsed metadata appears as chips below the box after submit.

### Task detail panel

Click a task in any list to open the right-hand **Task details** panel:

- **Title**, **description**, **priority** (P1–P4), **due** date/time
- **Duration** (minutes)
- **Project**, **section**, **parent task** (for subtasks)
- **Labels** — toggle chips on/off
- **Recurrence** and **Reminders** (see below)
- **Save** applies changes; **Delete task** is permanent (use **Ctrl+Z** to undo a recent delete in-session)

### Complete and subtasks

- Click the task checkbox, or focus a task and press **X** or **Space**.
- Completing a **parent** with open subtasks opens a dialog:
  - **Complete parent only** — children stay open
  - **Complete all children too** — one-shot cleanup
- **Recurring tasks:** completing advances **due** to the next occurrence and leaves the task open until the series ends. Clear recurrence first if you want a final completion.

Completed tasks are hidden by default. Use **Show completed** in the list header to reveal them (preference is remembered in this browser).

### Subtasks

From a project or Inbox list, add subtasks via the list UI (nested up to two levels below a top-level task). Set **Parent task** in the detail panel to move hierarchy.

### Undo

**Ctrl+Z** (Cmd+Z) reverses the last destructive action in this browser session (complete, delete, etc.). Delete undo recreates tasks with new IDs — not a true undelete.

---

## Quick-add tokens

Deterministic parser extracts metadata; leftover text becomes the title.

| Token type | Examples |
|------------|----------|
| Priority | `p1`, `P2`, `!3` (default P4) |
| Duration | `45m`, `1.5h`, `2d`, `1w`, `2mo` — `m` means minutes, not months |
| Due date/time | `today`, `tomorrow`, `next monday`, `2026-08-15`, `at 3pm`, `at 14:30` |
| Epic | `!!Organon`, `!!"Q3 Infrastructure"`, `epic:Auth` |
| Project / section | `#Dev`, `#"Client App"`, `#Dev/Backend` |
| Recurrence | `every monday, wednesday`, `every! 2 weeks from next week until end of year` |

**Example:**

```text
Review spec 1.5h p1 next Tue at 9am !!Organon #Dev/Backend
```

**Recurrence in quick-add:**

```text
Standup every monday, wednesday from 8/30 to 9/20
Pay rent every! month on the 1st
```

- **`every`** — next due slides from when you complete (flexible).
- **`every!`** — fixed calendar series (strict).
- Optional frame: `from …` / `to` / `until` / `through …` date bounds.

Label tokens in quick-add are not shipped; assign labels in task detail or the Labels screen.

---

## Labels

Open **Labels** in the sidebar.

| Task | Steps |
|------|--------|
| Create one | Name (stored lowercase) + color → **Create label** |
| Create many | One name per line, shared color → **Create labels** |
| Edit / delete | **✎** on a row → rename, recolor, or **Delete label** |

Deleting a label removes it from all tasks (confirmation shows task count). If the label is used, you can optionally **check other labels** to apply to those tasks before the pruned label is removed.

Sidebar **By label** links filter the task list. Toggle labels on tasks in the detail panel.

---

## Calendar

Open **Calendar** in the sidebar. Switch **Day** / **Week** and move with previous/next controls. Titles include day-of-year and ISO week numbers.

**Due markers** — Tasks with a due date/time appear as colored ticks on the grid (project color).

**Scheduled blocks** — Manual time blocks you place on the calendar:

1. **Click an empty time slot** → modal opens with start/end prefilled.
2. Pick a **task**, adjust times, optionally check **Pinned** (stored for future scheduler; no auto-move today).
3. **Save** creates the block. Blocks appear in **Today** / **Upcoming** when they overlap those windows.

**Edit or remove:** Click a block or due marker → modal → change times/task or **Delete**.

Calendar **drag** to move or resize is not shipped — use the modal. Month view is not shipped. No external calendar events yet.

---

## Recurrence

Set recurrence when creating (quick-add) or in **Task details → Recurrence**:

| Field | Purpose |
|-------|---------|
| **Pattern** | e.g. `every monday, wednesday` or `every! 2 weeks` |
| **From / Until** | Optional inclusive date frame |

Click **Save recurrence**. **Clear** removes the rule.

When you **complete** a recurring task:

- **`every`** — next due is computed from completion time.
- **`every!`** — next due follows the fixed schedule.
- When no next occurrence remains inside the frame, completion finishes the task normally.

To stop an unbounded series early: **Clear** recurrence, then complete.

---

## Reminders

In **Task details → Reminders**:

1. Set **When** (date and time).
2. Choose **Channel**:
   - **In-app toast** — banner inside thePlan while you are signed in
   - **Browser notification** — OS notification (requires permission)
3. Click **Add reminder**.

For browser notifications, click **Enable browser notifications** when prompted (or allow in browser site settings).

While signed in, the app polls for due reminders about every **30 seconds** (and when you refocus the tab). Fired reminders show a toast; browser-channel reminders also raise a system notification, then mark as delivered.

Remove upcoming reminders with **Remove** on each row.

Location reminders and push/mobile are not shipped.

---

## Search

Press **/** or use the top-bar search box. Results match task title and description; select a row to open task detail.

---

## Settings and themes

**Settings** (sidebar footer) opens a modal:

### Theme

Nine presets: Dark, Solarized Dark, Light, Solarized Light, Black, Forest, Midnight, Amethyst, Garnet.

### Custom colors

Optional hex overrides for background, panel, text, muted text, and accent. **Reset overrides** clears them. Choices persist in browser local storage (per browser, not synced across devices).

### Household

Visible only to **admin** accounts — see [Household accounts](#household-accounts-admin).

Entity color custom hex pickers on epics/projects/labels use preset swatches today; full `#RRGGBB` pickers on entities are deferred.

---

## Keyboard shortcuts

Press **?** anywhere (outside text fields) for the overlay, or use:

| Keys | Action |
|------|--------|
| **Q** or **Ctrl+K** | Focus quick-add |
| **/** | Focus search |
| **Ctrl+Z** | Undo last action |
| **J** / **K** or **↑** / **↓** | Move task focus in lists |
| **Enter** | Open focused task |
| **X** or **Space** | Complete / uncomplete focused task |
| **?** | Toggle shortcuts help |
| **Esc** | Close modals |

---

## Tips for daily use

1. **Use :8080** after Compose starts; bookmark it on each household device.
2. **Today** is your dashboard — due dates plus anything you blocked on the calendar for today count.
3. **Inbox** is for capture; move tasks to projects when you know where they belong.
4. **Passphrases** — a long memorable sentence is fine (12+ characters).
5. **Back up** before upgrades: run the backup script or pg_dump one-liner above.
6. **On a phone:** use the tunnel HTTPS URL; open the ☰ menu for views/projects. Task details fill the screen — close with ×. Calendar stays on **Day** mode on small screens.
7. **Remote access** (Cloudflare Tunnel / Access) is documented for operators in [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md).

---

## Wave 1.5 / next (brief)

Wave **1.5 exited 2026-08-10** — [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md). W1.6 phone UI included.

**Next:** Wave **2a** (Google Calendar) is in progress — then Scheduler (W2b). Everything else is W3+.

---

## Related docs

| Doc | Contents |
|-----|----------|
| [README.md](../README.md) | Compose quick start, dev setup, backup, tunnel |
| [CLOUDFLARE-TUNNEL.md](./CLOUDFLARE-TUNNEL.md) | Remote access via Cloudflare Tunnel / Access |
| [02-functional-spec.md](./02-functional-spec.md) | Full behavior spec |
| [03-feature-catalog.md](./03-feature-catalog.md) | Feature list by wave |
| [07-wave-roadmap.md](./07-wave-roadmap.md) | What ships next |
| [WAVE-1-EXIT.md](./WAVE-1-EXIT.md) | MVP exit record |
| [WAVE-1.5-EXIT.md](./WAVE-1.5-EXIT.md) | Wave 1.5 exit record |
| [CHANGELOG.md](../CHANGELOG.md) | Release notes |
