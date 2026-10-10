# Polish + deferred inventory (F1–F7 next-features)

**Filename:** POLISH-DEFERRED-2026-10-10.md  
**Created:** 2026-10-10  
**Author:** Steve (Discovery)  
**Status:** Open  
**Scope:** Docs reconcile + in-version deferred product work after F7 M1/M2 Dex+Trish path closed in evidence. **No implementation in this pass.** Parent commits uncommitted F7/M1–M2/docs separately.

**Sources:** [MANUAL-CHECKLIST.md](./MANUAL-CHECKLIST.md), [F4-TIME-MAP-OVERRIDES.md](./F4-TIME-MAP-OVERRIDES.md), [F5-COURSERA-TEMPLATES.md](./F5-COURSERA-TEMPLATES.md), [F6-REPLAN-PREVIEW.md](./F6-REPLAN-PREVIEW.md), [F7-SAVED-VIEWS.md](./F7-SAVED-VIEWS.md), [NEXT-FEATURES-SPEC.md](../NEXT-FEATURES-SPEC.md) §2 closeout/deferred, [DEX-F7-CHECKLIST-2026-10-10.md](./DEX-F7-CHECKLIST-2026-10-10.md), cross-checks vs [DEX-F5](./DEX-F5-MANUAL-2026-10-09.md) / [DEX-F6](./DEX-F6-MANUAL-2026-10-09.md) / [CHANGELOG.md](../../CHANGELOG.md).

---

## 1 Verdict

F1–F7 delivery code is largely landed; **no feature is Closed/shipped**. The highest leverage next work is a **Page polish pass** that stops the paper trail from lying (especially F7 M1/M2 and F5/F6 “awaiting Dex” residue), then a thin **product deferred** wave. Parked items stay out of this version.

---

## 2 Bucket A — Polish (docs / sign-off / reconcile)

Docs and checklist text that lag verified reality. **Owner: Page.** No product code. Safe immediately after parent’s commit lands (or against current tree if editing only status lines).

| ID | Item | Reality (evidence) | Stale / unfinished text |
|----|------|--------------------|-------------------------|
| **P-A1** | F7 M1/M2 + W3 completion gaps | Dex **2026-10-10:** load-more, mode PATCH, M1 sort, M2 reorder **verified closed** ([DEX-F7-CHECKLIST](./DEX-F7-CHECKLIST-2026-10-10.md) § M1/M2) | [MANUAL-CHECKLIST](./MANUAL-CHECKLIST.md) L14 still “Implemented, pending Dex retest”; [F7-SAVED-VIEWS](./F7-SAVED-VIEWS.md) W3 gaps table still “pending Dex”; [CHANGELOG](../../CHANGELOG.md) Unreleased F7 W3 completion “pending Dex retest” / status “Dex retest … remain” |
| **P-A2** | DEX-F7-CHECKLIST internal consistency | Top of file: M1/M2 PASS; open = household migration, automated W3, human acceptance | Lower “Resolution (pending Dex retest)” + “Checks left open” still say M1/M2 require retest — rewrite to **Verified closed** and keep only true opens |
| **P-A3** | F6 P2 row notes vs narrative | Checklist/Dex narrative: **three P2s Verified closed** (moved counts, planning lead / available-now, overlapping receipt); archive P1 closed | Several F6 checklist rows still “**P2 Fixed (code), awaiting Dex retest**” for items already closed; sign-off note muddles closed P2s with open R1 |
| **P-A4** | F6 P1 R1 `epic_id` / epic `target_date` | Tesla fix + **4** focused pytest green; **still awaiting Dex retest** | Keep as Open product/ops item (**B-F6-1**); polish only so it is the *only* remaining “awaiting Dex” callout in F6 headers |
| **P-A5** | F5 “awaiting Dex retest” on packaging / idempotency / module picker | F5 delivery + MANUAL header: **all seven findings + residuals verified closed** (Dex) | Per-row notes still “awaiting Dex retest” — flip to Verified closed; leave true PARTIAL operator rows (download, source-ref presentation, post-apply labels in browser) |
| **P-A6** | Sign-off table | Empty Done cells for Setup–F6; F7 = Open with notes | Refresh Notes columns to current dispositions; do **not** forge Trish “ok” — human gate stays human |
| **P-A7** | Setup migrate checkboxes | Operator evidence incomplete for **025** / **027** on household path | Tick only with evidence, or note “Dex disposable only” — do not imply household migrate done |
| **P-A8** | F5 CLI.md | Delivery says [CLI.md](../CLI.md) update **Open** | Page: confirm `templates` family documented; fill gaps if any |
| **P-A9** | F7 delivery wave-map vs latest gate | Status line mostly current; gap table lagging | Align W3 gap table + Page note with M1/M2 closed; F7 remains **Open** for migration + W3 tests + sign-off |
| **P-A10** | Cross-link stale FAIL language | Parent context: M1/M2 docs still saying FAIL in places | Grep delivery/CHANGELOG for FAIL / pending Dex on F7 M1/M2; replace with Verified closed + date |

**Polish exit:** Paper trail agrees that F7 M1/M2 are closed; F5 Dex findings closed; F6 only R1 (+ operator acceptance) still “awaiting”; F7/F4–F6 remain Open for real remaining work — not Closed.

---

## 3 Bucket B — Deferred product work (in-scope if she picks it up)

### B1 — F7 closeout (highest version-close pressure)

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F7-1** | Representative **existing-data** migration to **027** + v1 system predicate backfill | Tesla (+ Trish on data source) | Fresh DB only so far. Needs **isolated copy** of household (or anonymized dump) — never daily-driver. Document procedure + result. |
| **B-F7-2** | Automated **W3** regression suite | Renee (+ Andi for harness hooks) | Web unit already **14** for forest/reorder/predicate; missing committed coverage for filter modal, sidebar reorder, presentation PATCH, load-more, sort peer-order. Manual/Dex does not substitute. |
| **B-F7-3** | Human final acceptance / sign-off | Trish | Checklist rows checked = Dex evidence, not Closed. |
| **B-F7-4** | `GET /tasks?view=` convenience alias | — | Explicit **non-goal**; keep excluded unless she reopens. |

### B2 — F6 acceptance residue

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F6-1** | Dex retest P1 R1 — project **`epic_id`** reparent/detach + epic **`target_date`** lock+bump | Dex / ops (code already Tesla) | Unlocks honest F6 checklist flip from “awaiting Dex”. |
| **B-F6-2** | Operator manual rows still open / PARTIAL | Trish + Dex | W1 ready fields, apply paths, stale/expiry live spot-checks; many AUTOMATED PASS only. |
| **B-F6-3** | **F6-B–D** slice acceptance not fully closed | Jules/Tesla if gaps found; else Renee + operator | Pytest green ≠ slice accepted. After B-F6-1, decide ship-with-known-limitations vs more UX. |
| **B-F6-4** | W3 / F6-E operator-readable before/after polish | Andi | Modal landed; full readability open. |

### B3 — F4 deferred W3 remainder

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F4-1** | CLI override list/create/edit/delete | Jules or Tesla | Explicit W3 deferral; API already exists. |
| **B-F4-2** | Calendar **day-mode** override overlay | Andi | Week overlay Dex-verified; day not in scope yet. |
| **B-F4-3** | **F4-D** UX — red precedence, pins/busy disclosure, stale schedule indicators in UI | Andi (+ Jules if scheduler copy) | API empty-strict / week overlay partial; full F4-D open. |
| **B-F4-4** | Optional DST browser spot-check | Dex / Trish | Pytest matrix green; optional only. |

### B4 — F5 deferred / incomplete operator

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F5-1** | **Outline ↔ Templates panel merge** | Jules + Andi | Explicitly deferred; legacy `/outlines/*` stays. |
| **B-F5-2** | Remaining PARTIAL manual rows (example download, source-ref/warning presentation, post-apply label visibility in browser) | Andi / Dex | Quality green; operator polish. |

### B5 — Earlier-wave checklist residue (version hygiene, not new features)

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F2-*** | Work-board archived picker quirk; native Space dropdown open; drag peer/within-column; archived project detail browser | Andi / Dex | PARTIAL rows in MANUAL-CHECKLIST — disposition or finish. |
| **B-F3-polish** | Prerequisite titles (not UUIDs); overbooked vs prerequisite copy; `priority_ups` stale compare; schedule-run summary web | Jules / later | Listed under “Not on this gate” as F3 backlog / W3 — pick only if she wants polish inside this version. |

---

## 4 Bucket C — Explicitly parked / out of version

List only to **exclude** from this polish+deferred wave:

| Item | Source |
|------|--------|
| Desktop packaging / Tauri installer / LiveBytes distribution | NEXT-FEATURES-SPEC §2; ADR-009 |
| General template marketplace | Spec §2 |
| Coursera login / scraping / progress sync | Spec §2 / §8 |
| Autonomous replanning | Spec §2 |
| Team workspaces | Spec §2 |
| Automatic Squirrel Board updates | Spec §2 |
| F6 selective per-block apply; multi-scenario compare | Spec §9 design default |
| F6 unsaved hypothetical Time Map edits in preview | F6 delivery known limitations |
| Fourth Coursera “weekly study routine” template | Spec §8 |
| F7 free-form / NL query; snapshot task-id collections; Work/Calendar/Trash as `SavedFilter` | F7 non-goals |
| `GET /tasks?view=` alias | F7 deferred table / non-goal |
| Failed remote mirror delete as *open* work | DEF-028 **closed** 2026-10-09 — do not reopen |
| Push to GitHub / daily-driver household mutate for QA | Standing policy |

---

## 5 Proposed execution plan (ordered, parallel-safe)

Phase gates: Discovery (this brief) → Implementation → Quality → Documentation → Delivery. **Do not mark Closed until Renee exits Quality** (or Trish fail-and-hold-docs).

### Wave 0 — Polish docs (Page) — start first

**Size:** small (half-day class).  
**Files:** `MANUAL-CHECKLIST.md`, `F7-SAVED-VIEWS.md`, `DEX-F7-CHECKLIST-2026-10-10.md`, `CHANGELOG.md`, light touch `F5-COURSERA-TEMPLATES.md` / `F6-REPLAN-PREVIEW.md` / `DEX-F6-MANUAL-2026-10-09.md` status lines, optional `CLI.md`.  
**Parallelism:** alone first if parent commit still landing; else Page-only, no builder thrash.

### Wave 1 — Parallel product/ops (no shared hot files)

| Lane | Work | Owner | Touch zone |
|------|------|--------|------------|
| **1a** | F7 automated W3 suite | Renee (+ Andi fixtures) | `apps/web/tests/*`, maybe thin `api.ts` test hooks — avoid Sidebar/TaskList product edits unless bug found |
| **1b** | F6 Dex retest R1 (`epic_id` / `target_date`) | Dex | Disposable stack only; Page updates checklist after PASS |
| **1c** | F7 household migration procedure draft + isolated dry-run | Tesla | Alembic/runbook docs; **no** daily-driver |

Lanes 1a / 1b / 1c are file-disjoint if Renee stays in tests and Tesla stays in migration notes + isolated DB.

### Wave 2 — Trish-gated product deferred (pick after decisions in §6)

Ordered recommendation if she says “finish the version”:

1. **F4 CLI overrides** (Jules/Tesla) — API done; CLI parity matches F5/F7 pattern.  
2. **F4 day overlay** (Andi) — web-only, calendar files.  
3. **F4-D stale/red/pins UI** (Andi) — after day overlay or parallel if different components.  
4. **F6-E readability + remaining operator** (Andi + Trish).  
5. **F5 outline merge** — only if she explicitly wants it; otherwise stay deferred.  
6. **F2/F3 PARTIAL disposition** — finish critical UX or document known limitations for sign-off.

### Wave 3 — Human gates

Trish sign-off table + Combined scenarios in NEXT-FEATURES-SPEC §12 (esp. Disrupted week, Find it again) as time allows. Steve does not forge Closed.

---

## 6 Trish decisions needed

| # | Question | Recommendation |
|---|----------|----------------|
| **D1** | Do **F4 CLI + day overlay + F4-D** **block version close**, or disposition as **known deferral** with W3 Settings/week verified? | Default: **known deferral** if she wants to close the seven-feature wave sooner; schedule Wave 2 only if she wants F4 “complete.” |
| **D2** | Keep **F5 Outline merge** deferred for this version? | **Yes** — TemplatesPanel + `/templates/*` already distinct; merge is a product redesign. |
| **D3** | After Dex closes **F6 R1**, ship F6 with **F6-B–D “accepted with pytest + Dex”** or require full operator checklist green? | Prefer pytest + Dex R1 + spot-check apply path; leave selective-apply / hypothetical overrides parked. |
| **D4** | **F7 household migration:** anonymized dump / restore-to-isolated, or document “fresh-only verified” and accept residual risk? | Prefer isolated restore once; skip only with explicit known-limitation line. |
| **D5** | F1–F3 **PARTIAL** checklist rows: finish this version or sign with known limitations? | Sign with known limitations for non-blocking PARTIALs unless she hits them daily. |

---

## 7 Recommended first Implementation slice

After Wave 0 Page polish (or in parallel once commit lands):

**Kick: B-F7-2 — Automated W3 suite (Renee).**

Why: concrete, no Trish data decision, closes a hard Open line in F7 delivery and DEX checklist, does not thrash Jules/Andi product files if scoped to tests first, and Quality gate is Renee’s lane. Immediate second ops kick if capacity: **B-F6-1 Dex retest** (unblocks F6 paper).

---

## 8 Return path for parent

| Field | Value |
|-------|--------|
| Brief | `docs/delivery/POLISH-DEFERRED-2026-10-10.md` (Open) |
| First Implementation kick | **Renee: F7 automated W3 regression suite** (`B-F7-2`) |
| Blocking decisions | **D1** F4 remainder vs known deferral; **D4** household migration approach |

**Not done here:** code, commits, Closed marks, push.
