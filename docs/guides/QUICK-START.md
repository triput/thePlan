# thePlan — Quick Start

**For:** friends poking around Trish's live instance (e.g. [plan.silverhelmet.com](https://plan.silverhelmet.com)).

**Not for:** standing up Docker, env files, migrations, OAuth console work, or tunnel ops — Trish already did that. You got credentials separately; this doc is what to click once you're in.

For operator/runbook stuff, see [USER-GUIDE.md](../USER-GUIDE.md) and the root [README](../../README.md).

---

## What is thePlan?

thePlan is Trish's personal execution app — Todoist-style hierarchy and capture, plus SkedPal-ish scheduling primitives (Time Maps, Plans, calendar blocks). It's **local-first-ish**: your data lives on her stack, the UI is fast and optimistic, and Google Calendar can overlay **busy** time so manual planning doesn't pretend meetings don't exist.

There is **no karma**, **no streaks**, and **no team assignees**. Just tasks, time, and a calendar that eventually wants to auto-schedule things (that last bit isn't live yet — see [What's not ready](#whats-not-ready-yet)).

---

## Sign in

1. Open the URL Trish gave you.
2. Enter **username or email** and your **password/passphrase** (12+ characters; spaces are fine).
3. Click **Sign in**.

Your session stays until you **Sign out** (top-right, next to your display name).

### Household accounts (the short version)

One thePlan deployment can host **multiple personal accounts** — spouse, friend, housemate — each with **completely separate** tasks, projects, labels, and calendar data. Trish is the operator; you're a guest with your own login. There are no shared projects or assignees: if you want someone to see a task, you tell them about it like it's 2009.

If Trish set you up with the demo user **`nebula`**, that's seeded sample data for kicking tires without polluting her admin account.

---

## Layout tour

```
┌ Sidebar ──────────────┬─ Top bar: Quick-add | Search | ? | You | Sign out ─┐
│ Views                 ├─ Main: task list, calendar, or labels ─────────────┤
│  Inbox / Today / …    │                                                  │
│  Labels               │  [Task detail panel when a task is selected]      │
│  Epics & projects     │                                                  │
│ Settings (footer)     └──────────────────────────────────────────────────┘
```

| Area | What it does |
|------|----------------|
| **Sidebar — Views** | Jump to Inbox, Today, Upcoming, Calendar, Labels, or label-filtered lists |
| **Sidebar — Epics & projects** | Browse hierarchy; click a project or epic to filter tasks |
| **Top bar — Quick-add** | Capture tasks from anywhere with optional magic tokens |
| **Top bar — Search** | Find tasks by title/description |
| **Top bar — ?** | Keyboard shortcuts cheat sheet |
| **Main pane** | Task list, calendar grid, or label management |
| **Task detail panel** | Edit everything about one task (right side on desktop; full-screen sheet on phone) |
| **Settings** | Gear at sidebar footer — themes, scheduling defaults, Time Maps, Plans, Google Calendar |

**On a phone:** tap **☰** for the drawer nav. Calendar sticks to **Day** mode; task detail takes over the screen until you close it.

---

## Smart views

Fixed system views — no custom filter language yet.

| View | What you see |
|------|----------------|
| **Inbox** | Incomplete tasks with **no project** — the capture bucket |
| **Today** | Incomplete tasks **due today** *or* with a **scheduled block** overlapping today (calendar placement counts even without a due date) |
| **Upcoming** | Incomplete tasks due or blocked in the next **7 days** (horizon configurable in Settings), sorted soonest-first |
| **Calendar** | Day/week time grid — due markers, your blocks, Google busy overlays |
| **Labels** | Create/rename/recolor/delete labels without opening a task |
| **By label** | Sidebar links when you have labels — filtered task lists |
| **Project** | Click any project — tasks grouped by section |
| **Epic** | Click an epic title — rollup of all tasks in projects under that epic |

Use **Show completed** in the list header to reveal finished tasks (dimmed). The toggle is remembered in your browser.

---

## Tasks

### Create a task

**Fastest:** top-bar **quick-add** — type a title, optional tokens (see [Quick-add](#quick-add--natural-language)), press **Enter**. Parsed metadata shows as chips below the box.

**Context-aware defaults:** on a **project** view, new tasks land in that project unless tokens override. On **Inbox**, they stay inbox unless you tag `#Project`.

**From a list:** use **Add subtask** (+ icon on a row) for nested work.

### Task detail panel

Click any task to open **Task details**:

| Field | Meaning |
|-------|---------|
| **Title / Description** | Plain text for now (no markdown rendering yet) |
| **Priority** | P1 (urgent) → P4 (default chill) |
| **Due** | When you'd like it done — shows on calendar as a due marker |
| **Soft target** | Flexible plan target — scheduler *may* slide this later |
| **Deadline** | Hard commit — scheduler must not miss (when auto-schedule exists) |
| **Plan** | Bind a named Plan; may copy its soft target onto the task |
| **Duration** | Estimated minutes (defaults from Settings if omitted on create) |
| **Time Map** | Preferred window (Morning/Afternoon/Evening or custom) |
| **Project / Section / Parent** | Placement in hierarchy |
| **Labels** | Toggle chips on/off |
| **Recurrence / Reminders** | See below |

Click **Save** to apply. **Delete task** is permanent — but see [Undo](#undo).

### Complete and subtasks

- Checkbox on the row, or focus a task and press **X** or **Space**.
- **Parent with open children:** dialog offers **Complete parent only** or **Complete all children too**.
- **Recurring tasks:** completing advances **due** to the next occurrence and keeps the task open. Clear recurrence first if you want a final done.
- **Subtasks:** up to **two** levels below a top-level task (task → subtask → nested subtask). Set **Parent task** in detail to move hierarchy.

### List badges

Tasks show compact badges when relevant: priority, due, **Plan** name, **Soft** target, **Deadline**, duration.

---

## Quick-add & natural language

Focus with **Q** or **Ctrl+K** (Cmd+K on Mac). The parser pulls metadata; leftover text becomes the title.

| Token type | Examples |
|------------|----------|
| Priority | `p1`, `P2`, `!3` (default P4) |
| Duration | `45m`, `1.5h`, `2d`, `1w`, `2mo` — **`m` = minutes**, not months |
| Due date/time | `today`, `tomorrow`, `next monday`, `2026-08-15`, `at 3pm`, `at 14:30` |
| Epic | `!!Organon`, `!!"Q3 Infrastructure"`, `epic:Auth` |
| Project / section | `#Dev`, `#"Client App"`, `#Dev/Backend` |
| Recurrence | `every monday, wednesday`, `every! 2 weeks from next week until end of year` |
| Time Map | `@morning`, `@afternoon`, `@evening` — bind default seed windows when they exist |

**Example:**

```text
Review spec 1.5h p1 next Tue at 9am !!Organon #Dev/Backend @morning
```

**Recurrence examples:**

```text
Standup every monday, wednesday from 8/30 to 9/20
Pay rent every! month on the 1st
```

- **`every`** — next due slides from when you complete (flexible).
- **`every!`** — fixed calendar series (strict).
- Optional frame: `from …` / `to` / `until` / `through …`.

Label tokens in quick-add are **not** shipped — assign labels in task detail or the Labels screen.

---

## Epics, projects, and sections

**Epics** — multi-month initiatives. Expand/collapse in the sidebar; click the epic name for an aggregate task view across its projects. **+** on an epic adds a project.

**Projects** — day-to-day buckets. Standalone projects (no epic) and epic children both appear in the sidebar. Click to open the project list. **✎** edits title, color, archive; arrow buttons reorder.

**Sections** — visual groupings *inside* a project. On a project view, section tags appear above the list; tasks group under their section. Create/edit sections from the project UI.

**Inbox** — tasks with no project. Capture first, organize later.

**Archive** — archived epics/projects hide from default lists but aren't deleted.

---

## Labels

Open **Labels** in the sidebar.

| Task | How |
|------|-----|
| Create one | Name (stored **lowercase**) + color → **Create label** |
| Create many | One name per line, shared color → **Create labels** |
| Edit / delete | **✎** on a row |

Deleting a label removes it from all tasks (confirmation shows count). If the label is in use, you can optionally **reassign** affected tasks to other labels first.

Toggle labels on tasks in the detail panel. Sidebar **By label** links open filtered lists.

---

## Calendar

Open **Calendar** in the sidebar.

### Views and navigation

- **Day** and **Week** modes (week hidden on narrow phone screens — day only).
- Previous/next arrows; titles include **day-of-year** and **ISO week** numbers because Trish appreciates pedantry.
- **6A–10P / 24h** toggle in the header (or **Settings → Calendar display**) — default is 6 AM–10 PM.

### What's on the grid

| Layer | What it is |
|-------|------------|
| **Due markers** | Tasks with a **due** date/time — colored tick/dot (project color) |
| **Scheduled blocks** | Manual time blocks you placed for a task — solid blocks |
| **Google busy** | External calendar events (read-only gray blocks) — meetings, holds, life |
| **Pinned blocks** | Your blocks marked **Pinned** — styled distinctly; won't move on future replan |

### Interactions

**Desktop:**

- **Drag** a due marker to change its due time.
- **Drag** a scheduled block to move it; **drag the bottom edge** to resize.
- **Click empty slot** → modal to pick task, start/end, optional **Pinned**.

**Phone / narrow:**

- Tap slot or block → **modal** edit (no drag).

Blocks you place today show up in **Today** even without a due date.

### Conflicts

When a scheduled block or pinned placement overlaps **Google busy** time, the UI flags **schedule conflicts** — a banner count plus conflict styling on the overlapping items. This is visual awareness today; the auto-scheduler isn't rewriting your calendar yet.

### Google Calendar overlays (what you'll see)

If **your account** (or Trish's, if you're browsing her login) has Google connected:

- **Busy events** from subscribed calendars appear as read-only blocks.
- **Primary calendar** — drives busy/capacity semantics; one primary per connected Google account.
- **Informational calendars** — extra overlays (e.g. holidays, shared read-only cals) without treating them as capacity unless marked primary.
- **Push time blocks to Google** — optional mirror: local scheduled blocks can push to the primary Google calendar when enabled.

If nobody connected Google on this account, you only see thePlan tasks and manual blocks — no external busy. Connecting is optional per user in **Settings → Google Calendar → Connect Google Calendar** (OAuth in-browser; Trish handles server-side credentials).

Use **Sync now** after changing subscriptions. Pick calendars, mark one **primary**, save.

---

## Time Maps

**Settings → Time Maps** — named recurring windows when certain work *prefers* to happen (SkedPal "focus windows").

New accounts get seed maps: **Morning**, **Afternoon**, **Evening** (with quick-add tokens `@morning`, `@afternoon`, `@evening`).

Each map has:

- **Name**
- **Start / end time** (local)
- **Days of week**
- **Hard vs soft** — hard = stricter constraint for future scheduler; soft = preference

**Bind on a task:** Task details → **Time Map** dropdown, or quick-add tokens.

v1 is **one contiguous band per map**. Painted multi-band maps (green/yellow/red tiers on one map) are not shipped yet.

---

## Plans

**Settings → Plans** — named **soft frames** ("this week", "Thursday morning", "before trip").

Each Plan has a **name** and optional **soft target** datetime. Plans are flexible: the future scheduler may slide work within them.

**Bind on a task:** Task details → **Plan** picker. Assigning a plan **may copy** its soft target onto the task (you can still edit soft target afterward).

**Soft vs hard on tasks:**

| Field | Semantics |
|-------|-----------|
| **Soft target** / **Plan** | "I'd like this around then" — relaxable |
| **Deadline** | "Must not miss" — hard commit for scheduler |
| **Due** | Classic due date — visibility + urgency; distinct from deadline |
| **Pinned block** | "Do it at this clock time" — immovable on replan |

List rows show **Plan …**, **Soft …**, and **Deadline …** badges when set.

---

## Settings (user-facing bits)

Open **Settings** from the sidebar footer.

### Theme

Nine presets (Dark, Solarized variants, Light, Black, Forest, Midnight, Amethyst, Garnet). Optional **custom hex overrides** for background, panel, text, muted, accent — stored in **this browser** only.

### Scheduling defaults

Account-level planner knobs:

| Setting | What it means for you |
|---------|----------------------|
| **Timezone** | "Today" boundaries and displayed times (IANA string, e.g. `America/Los_Angeles`) |
| **Locale** | Formatting preference |
| **Workday / workweek** | Converts multi-day duration estimates (8h day, 5-day week defaults) |
| **Buffer between blocks** | Minutes the scheduler will leave between auto blocks (default 5) |
| **Upcoming horizon** | Days **Upcoming** looks ahead |
| **Default task duration** | Used when quick-add/create omits duration |
| **Default min block length** | Smallest slice size for future auto-scheduling |
| **Default schedule style** | **Standalone** (default), **Time block**, or **Bundle** — opt-in styles for future worker |
| **Auto-defer missed plan windows** | When on, missed soft plan targets may slide later instead of going stale |

These matter most once **Update Schedule** exists; they're still useful now for consistent defaults.

### Calendar display

**Show 24 hours** — full-day grid vs 6 AM–10 PM.

### Household (admin only)

If you're not Trish's admin account, you won't see this section. Operators manage users/passwords here.

---

## Recurrence

Set in quick-add or **Task details → Recurrence**:

| Field | Purpose |
|-------|---------|
| **Pattern** | e.g. `every monday, wednesday` or `every! 2 weeks` |
| **From / Until** | Optional date frame |

**Save recurrence** applies; **Clear** removes the rule.

Completing rolls **due** forward per `every` vs `every!` rules. To end an unbounded series: clear recurrence, then complete.

---

## Reminders

**Task details → Reminders:**

1. **When** — date and time.
2. **Channel** — **In-app toast** (banner while signed in) or **Browser notification** (needs permission).
3. **Add reminder**.

The app polls about every **30 seconds** (and on tab focus). **Remove** clears upcoming reminders.

No location reminders, no mobile push — web only.

---

## Search

Press **/** or use the search box. Matches title and description; click a result to open task detail.

---

## Undo

**Ctrl+Z** (Cmd+Z) reverses the last destructive action in this browser session — complete/uncomplete, delete, etc.

Delete undo **recreates** tasks with new IDs (not a true server-side undelete). Still beats "oops" followed by manual re-entry.

---

## Keyboard shortcuts

Press **?** for the overlay. Highlights:

| Keys | Action |
|------|--------|
| **Q** / **Ctrl+K** | Focus quick-add |
| **/** | Focus search |
| **Ctrl+Z** | Undo |
| **J** / **K** or **↑** / **↓** | Move task focus in lists |
| **Enter** | Open focused task |
| **X** / **Space** | Complete / uncomplete |
| **?** | Shortcuts help |
| **Esc** | Close modals |

---

## What's not ready yet

Don't go hunting for these — they're real roadmap, not hidden beta:

- **Update Schedule** — SkedPal-style "replan my week" button and async auto-scheduler worker
- **Auto time-blocking** — UPS scoring, slice/fit, dependency-aware ordering
- **Painted Time Maps** — one map with green/yellow/red preference tiers on the week grid
- **Time Map temporary overrides** — vacation/conference dated exceptions
- **Sidebar → calendar drag** — drop a task from the list onto a slot to block time
- **Custom saved filters / query language** — only fixed smart views today
- **Kanban board**, **voice input**, **email-to-task**, **Todoist import**, **Microsoft Calendar**
- **True task undelete** — undo recreates; server soft-delete restore is W2b+ 
- **Markdown** in descriptions, **location reminders**, **mobile app**

Wave status detail: [07-wave-roadmap.md](../07-wave-roadmap.md).

---

## Tips for guests

1. **Today** is the daily dashboard — due dates *and* calendar blocks on today both count.
2. **Inbox** is for brain-dump; sort into projects when you know where things live.
3. Try **quick-add tokens** once — they're deterministic, not AI, which means fewer surprises.
4. On desktop, **calendar drag** is the fast path for moving blocks; phones use the modal.
5. Connect **your own Google** in Settings if you want busy overlays on *your* account — Trish's connection doesn't leak into yours (household isolation).
6. **P1** is "actually important," not "I felt spicy when typing."

---

## Related docs

| Doc | Contents |
|-----|----------|
| [USER-GUIDE.md](../USER-GUIDE.md) | Operator guide — Compose, backup, tunnel, household admin |
| [02-functional-spec.md](../02-functional-spec.md) | Full behavior spec |
| [03-feature-catalog.md](../03-feature-catalog.md) | Feature inventory by wave |
| [07-wave-roadmap.md](../07-wave-roadmap.md) | What's shipped vs next |
