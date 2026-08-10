# Color Palette

Entity colors (epics, projects, labels) and UI chrome guidance for the application. Sourced primarily from **Synesis** theme tokens and account swatches and **Phronesis** cockpit/status accents, with a few Todoist-familiar extras for breadth. Custom `#RRGGBB` remains always allowed.

Client constants should expose the **Entity presets** table below in color pickers. App shell themes ship in **thePlan web** (`apps/web`): five named presets (Dark, Solarized Dark, Light, Solarized Light, Black) with optional custom hex overrides persisted in `localStorage`.

---

## Entity presets (MVP color picker)

Use these named swatches for epic, project, and label pickers. Order is the recommended picker order.

| ID | Name | Hex | Provenance |
|----|------|-----|------------|
| `teal` | Teal | `#0A7A6E` | Synesis light accent |
| `emerald` | Emerald | `#0A8558` | Synesis light / Phronesis completed |
| `mint` | Mint | `#059669` | Phronesis hybrid accent |
| `lime` | Lime | `#4D7C0F` | Synesis account swatch |
| `azure` | Azure | `#1668C4` | Synesis light |
| `sky` | Sky | `#0369A1` | Synesis account swatch |
| `indigo` | Indigo | `#4556B8` | Synesis light |
| `violet` | Violet | `#6D3FC9` | Synesis light amethyst |
| `grape` | Grape | `#7C3AED` | Synesis account swatch |
| `orchid` | Orchid | `#8E5FC0` | Phronesis light accent |
| `coral` | Coral | `#C23144` | Synesis light |
| `rose` | Rose | `#BE185D` | Synesis account / Phronesis overdue family |
| `amber` | Amber | `#B45309` | Synesis account / Phronesis blocked family |
| `terracotta` | Terracotta | `#C2410C` | Synesis account swatch |
| `charcoal` | Charcoal | `#635F75` | Synesis light muted |
| `slate` | Slate | `#64748B` | Phronesis backlog / neutral |

**Always available:** custom hex input `#RRGGBB` (validated 7-char).

### Schema defaults

| Entity | Default hex | Rationale |
|--------|-------------|-----------|
| Epic | `#6D3FC9` (`violet`) | Initiative-level accent from Synesis amethyst |
| Project | `#0A8558` (`emerald`) | Work-domain accent aligned with Phronesis/Synesis emerald |
| Label | `#635F75` (`charcoal`) | Neutral tag color |

---

## Priority colors (UI only — not stored as hex)

Map P1–P4 to fixed UI tokens (not user-editable entity colors):

| Priority | Suggested hex | Notes |
|----------|---------------|-------|
| P1 | `#C23144` | Coral — highest urgency |
| P2 | `#B45309` | Amber |
| P3 | `#1668C4` | Azure |
| P4 | `#635F75` | Charcoal / muted |

---

## Due & status accents (calendar / lists)

Borrowed from Phronesis due/status tokens for familiarity across the suite:

| Role | Hex | Notes |
|------|-----|-------|
| Due soon | `#D97706` | Phronesis light `--due-soon` |
| Overdue | `#C90F56` | Phronesis light `--due-overdue` |
| Planned / scheduled | `#0284C7` | Phronesis light planned |
| In progress / active block | `#3EBB6A` | Phronesis light progress |
| Completed (dim) | `#059669` | Keep muted in completed rows |

---

## Chrome themes (shipped)

**thePlan web** exposes five named presets in Settings. Default on first load: **Dark** (Phronesis Hybrid Dark tokens). Overrides persist under `theplan.theme` and `theplan.theme.overrides`.

| Preset | Source | `--bg` | `--panel` | `--accent` | `--text` | `--error` |
|--------|--------|--------|-----------|------------|----------|-----------|
| Dark | Phronesis hybrid | `#0B0F19` | `#121827` | `#059669` | `#E6EAF2` | `#F87171` |
| Solarized Dark | Phronesis | `#002B36` | `#073642` | `#A57BD5` | `#DDE5D8` | `#E34E80` |
| Light | Phronesis | `#F5F7FB` | `#FFFFFF` | `#8E5FC0` | `#1B2430` | `#C90F56` |
| Solarized Light | Phronesis | `#FDF6E3` | `#EEE8D5` | `#7F53B3` | `#334155` | `#B2185B` |
| Black | Synesis | `#0A0A0C` | `#121214` | `#C084FC` | `#E8E8EC` | `#FB7185` |

CSS variables also include `--panel-hover`, `--border`, `--text-muted`, `--accent-hover`, `--sidebar`, and `--danger`. Sister-app reference tables:

- `F:\Code Repo\Synesis\lib\theme\theme_tokens.dart`
- `F:\Code Repo\Phronesis\phronesis_app\static\phronesis\themes.css`
- `apps/web/src/theme.ts` — canonical preset definitions for the web client

---

## Non-goals

- No gamification badge colors or streak chrome.
- Do not force purple-on-white as the only brand look; emerald/teal remain first-class (Phronesis hybrid default).
- Entity presets are independent of chrome theme — hex values stay constant across light/dark shells.
