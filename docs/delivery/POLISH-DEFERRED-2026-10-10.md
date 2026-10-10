# Polish + deferred inventory (F1–F7 next-features)

<!--
==============================================================================
  File: docs/delivery/POLISH-DEFERRED-2026-10-10.md
  Description: Wave 0 polish + Wave 1 deferred product inventory after F7 M1/M2 evidence.
  Component: Docs/Delivery
  Version: 1.0
  Created: 2026-10-10
  Last Update: 2026-10-10 (Page — W1-R1 + IM-R1 Dex verified closed)
==============================================================================
-->

**Author:** Steve (Discovery)  
**Status:** Wave 0 polish **complete** (Page **2026-10-10**); **Wave 1 product deferred landed** (Page **2026-10-10**) — **not Closed**; Bucket B/C remainder **Open**  
**Scope:** Docs reconcile + in-version deferred product work after F7 M1/M2 Dex+Trish path closed in evidence. Wave 1 implementation landed locally; this pass updates paper trail only.

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
| **P-A4** | F6 P1 R1 `epic_id` / epic `target_date` | **Verified closed** Wave 1 retest **2026-10-10** ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md)) | **B-F6-1 closed**; polish F6 headers that still say “awaiting Dex retest” |
| **P-A5** | F5 “awaiting Dex retest” on packaging / idempotency / module picker | F5 delivery + MANUAL header: **all seven findings + residuals verified closed** (Dex) | Per-row notes still “awaiting Dex retest” — flip to Verified closed; leave true PARTIAL operator rows (download, source-ref presentation, post-apply labels in browser) |
| **P-A6** | Sign-off table | **Done 2026-10-10:** Trish authorized Page to stamp **10/10/26 OK** Setup–F7 | Notes retain **not Closed** where PARTIAL/operator residue remains |
| **P-A7** | Setup migrate checkboxes | **025** still fresh-disposable only (F6 R1 **verified closed** on Wave 1 retest; household path open). **027** **B-F7-1 closed** Trish **2026-10-10** (fresh + synthetic); household dump not required | **027** ticked with disposition note; leave **025** unchecked until household or explicit accept |
| **P-A8** | F5 CLI.md | Delivery says [CLI.md](../CLI.md) update **Open** | Page: confirm `templates` family documented; fill gaps if any |
| **P-A9** | F7 delivery wave-map vs latest gate | Status line mostly current; gap table lagging | Align W3 gap table + Page note with M1/M2 closed + **B-F7-1 dispositioned**; Trish Done **2026-10-10**; F7 **not Closed** (non-goal alias) |
| **P-A10** | Cross-link stale FAIL language | Parent context: M1/M2 docs still saying FAIL in places | Grep delivery/CHANGELOG for FAIL / pending Dex on F7 M1/M2; replace with Verified closed + date |

**Polish exit:** Paper trail agrees that F7 M1/M2 are closed; F5 Dex findings closed; F6 only R1 (+ operator acceptance) still “awaiting”; F7/F4–F6 remain Open for real remaining work — not Closed.

---

## 3 Bucket B — Deferred product work (in-scope if she picks it up)

### B1 — F7 closeout (highest version-close pressure)

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F7-1** | Representative **existing-data** migration to **027** + v1 system predicate backfill | Tesla (+ Trish) | **Closed (disposition, Trish 2026-10-10):** fresh disposable migrate (Dex) + synthetic pre-027 dry-run **passed** — [F7-MIGRATION-VERIFY.md](./F7-MIGRATION-VERIFY.md). Household dump **not** required. Daily-driver untouched. Trish Done sign-off **2026-10-10**; F7 **not Closed/shipped**. |
| **B-F7-2** | Automated **W3** regression suite | Renee (+ Andi for harness hooks) | **Landed (Quality):** web `npm test` **36** green — W3 regression suite. Trish Done **2026-10-10**; F7 **not Closed/shipped**. |
| **B-F7-3** | Human final acceptance / sign-off | Trish | **Done 2026-10-10:** [MANUAL-CHECKLIST § Sign-off](./MANUAL-CHECKLIST.md#sign-off) **10/10/26 OK** Setup–F7 (authorized). Done ≠ Closed/shipped. |
| **B-F7-4** | `GET /tasks?view=` convenience alias | — | Explicit **non-goal**; keep excluded unless she reopens. |

### B2 — F6 acceptance residue

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F6-1** | Dex retest P1 R1 — project **`epic_id`** reparent/detach + epic **`target_date`** lock+bump | Dex / ops (code already Tesla) | **Closed 2026-10-10** — Wave 1 retest **37** API tests ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md)). |
| **B-F6-2** | Operator manual rows still open / PARTIAL | Trish + Dex | W1 ready fields, apply paths, stale/expiry live spot-checks; many AUTOMATED PASS only. |
| **B-F6-3** | **F6-B–D** slice acceptance not fully closed | Jules/Tesla if gaps found; else Renee + operator | Pytest green ≠ slice accepted. After B-F6-1, decide ship-with-known-limitations vs more UX. |
| **B-F6-4** | W3 / F6-E operator-readable before/after polish | Andi | Modal landed; full readability open. |

### B3 — F4 deferred W3 remainder

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F4-1** | CLI override list/create/edit/delete | Jules or Tesla | **Dex verified closed 2026-10-10** — operator CRUD ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md)). Trish Done **2026-10-10**; F4 **not Closed** (optional DST). |
| **B-F4-2** | Calendar **day-mode** override overlay | Andi | **Dex verified closed 2026-10-10**; week overlay prior Dex-verified baseline. |
| **B-F4-3** | **F4-D** UX — red precedence, pins/busy disclosure, stale schedule indicators in UI | Andi (+ Jules if scheduler copy) | **Dex verified closed 2026-10-10** incl. **W1-R1** volume stale; Trish Done **2026-10-10**; F4 **not Closed**. |
| **B-F4-4** | Optional DST browser spot-check | Dex / Trish | Pytest matrix green; optional only. |

### B4 — F5 deferred / incomplete operator

| ID | Item | Owner | Notes |
|----|------|--------|-------|
| **B-F5-1** | **Outline ↔ Templates panel merge** | Jules + Andi | **Dex verified closed 2026-10-10** (**IM-R1**): [`ImportPanel.tsx`](../../apps/web/src/components/ImportPanel.tsx) — [DEX-IMPORT-VOLUME](./DEX-IMPORT-VOLUME-2026-10-10.md). Trish Done **2026-10-10**; F5 **not Closed** (PARTIAL operator rows). |
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

**Exit (2026-10-10):** Lanes **1a**, **1b**, **1c**, **1d**, and **B-F5-1** Dex retests **verified closed** — **no feature Closed/shipped**. **W1-R1** volume stale + **IM-R1** Import draft retention closed on [DEX-IMPORT-VOLUME](./DEX-IMPORT-VOLUME-2026-10-10.md). Trish Done sign-off **2026-10-10** (Setup–F7); PARTIAL/operator residue unchanged.

| Lane | Work | Owner | Touch zone | Disposition |
|------|------|--------|------------|-------------|
| **1a** | F7 automated W3 suite | Renee (+ Andi fixtures) | `apps/web/tests/*` | **Done (Quality):** `npm test` **36** green — F7 W3 regression; Trish Done **2026-10-10**; F7 **not Closed** |
| **1b** | F6 Dex retest R1 (`epic_id` / `target_date`) | Dex | Disposable stack only | **Closed 2026-10-10** — Wave 1 retest |
| **1c** | F7 migration verify (fresh + synthetic) | Tesla | Alembic/runbook docs; **no** daily-driver | **Dispositioned (Trish 2026-10-10):** **B-F7-1** closed — household dump not required |
| **1d** | F4 CLI + day overlay + F4-D UI slice | Jules/Tesla + Andi | CLI `overrides`; web calendar/day + F4-D chrome | **Dex verified closed 2026-10-10**; Trish Done **2026-10-10**; F4 **not Closed** |

Lanes 1a / 1b / 1c remain file-disjoint; **1d** docs updated in [F4-TIME-MAP-OVERRIDES](./F4-TIME-MAP-OVERRIDES.md) and [CLI.md](../CLI.md).

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
| **D2** | Keep **F5 Outline merge** deferred for this version? | **Superseded 2026-10-10 (Trish):** merge **Implemented** — **B-F5-1** [`ImportPanel`](../../apps/web/src/components/ImportPanel.tsx); Dex closed; Trish Done **2026-10-10**; F5 **not Closed** (PARTIAL operator). |
| **D3** | After Dex closes **F6 R1**, ship F6 with **F6-B–D “accepted with pytest + Dex”** or require full operator checklist green? | Prefer pytest + Dex R1 + spot-check apply path; leave selective-apply / hypothetical overrides parked. |
| **D4** | **F7 household migration:** anonymized dump / restore-to-isolated, or document “fresh-only verified” and accept residual risk? | **Decided 2026-10-10 (Trish):** accept **fresh + synthetic** — **B-F7-1 closed (disposition)**; household dump not required. Optional runbook remains in [F7-MIGRATION-VERIFY.md](./F7-MIGRATION-VERIFY.md). |
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
| Brief | `docs/delivery/POLISH-DEFERRED-2026-10-10.md` — Wave 0 done; **Wave 1 landed (not Closed)** Page **2026-10-10** |
| Wave 1 landed | **B-F7-2** (36 web tests); **B-F4-1/2/3** + **B-F6-1** + **B-F5-1** (**IM-R1**) + **W1-R1** — **Dex verified closed 2026-10-10**; Trish Done sign-off **2026-10-10** (Setup–F7) |
| Next kicks | F5 PARTIAL operator rows; optional F4 DST browser; F6 W3 operator + F6-B–D acceptance; Combined scenarios §12 |
| Blocking decisions | **D4** decided (**B-F7-1** closed); **D2** superseded (**B-F5-1** Dex closed); **D1** superseded — F4 Wave 1 Dex green; Trish Done **2026-10-10** — features **not Closed** where PARTIAL residue remains |

**Not done here:** Closed/shipped marks without policy, push.
