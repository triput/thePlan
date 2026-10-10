# F5 — Coursera templates

**Latest Dex gate, 2026-10-10:** **B-F5-1 / IM-R1 verified closed** — Import tab draft, edited preview, receipt, and idempotency key survive tab navigation; template dropdown change intentionally reseeds. Web **36/36** + build green. [Evidence](DEX-IMPORT-VOLUME-2026-10-10.md). Trish Done sign-off **2026-10-10**; PARTIAL operator rows unchanged — **not Closed**.

<!--
==============================================================================
  File: docs/delivery/F5-COURSERA-TEMPLATES.md
  Description: F5 Coursera templates delivery tracker — waves, B-F5-1 Import merge.
  Component: Docs/Delivery
  Version: 1.1
  Created: 2026-10-09
  Last Update: 2026-10-10 (Page — B-F5-1 / IM-R1 Dex verified closed)
==============================================================================
-->

**Status:** **W1 Implemented** · **Quality:** API pytest **21** green — W1 **14** + F5-B **7** (`test_f5_w1_templates.py`, `test_f5_b_templates.py`; **2026-10-09**, Renee exit; W1 includes apply-route **commit** fix) · CLI **`templates list|get`** green · IBM apply **417** tasks · **W2 Implemented** (CLI `templates` list/get/propose/apply/receipt — Jules, working tree) · **W3 Implemented** ( **`TemplatesPanel`** + **`OutlineImportPanel`** embedded in unified **`ImportPanel`** — Andi/Jules **2026-10-10**, web build green) · **B-F5-1 Dex verified closed (2026-10-10):** one **Import** modal with **Templates** / **Custom outline** tabs ([`ImportPanel.tsx`](../../apps/web/src/components/ImportPanel.tsx)); **`/api/v1/templates/*`** and legacy **`/api/v1/outlines/*`** both kept · push **not requested** · F5 **Open / in-progress** — **not** Closed/shipped ([manual checklist](./MANUAL-CHECKLIST.md), Trish Done **2026-10-10**; PARTIAL operator rows open — **not Closed**)

**Spec:** [NEXT-FEATURES-SPEC.md §8](../NEXT-FEATURES-SPEC.md#8-f5-coursera-templates)  
**Build:** working tree on `cursor` `main` (F5 API + CLI + W3 web + B-F5-1 Import shell local)  
**Hygiene:** No F5-specific migration — reuses F1 **`handoff_receipts`** with `operation_kind` **`template_apply`**; Alembic head **`027_saved_filter_presentation`** (F7) or **`024_time_map_overrides`** minimum for F5-only checks

## Wave map

| Wave | Scope | Status |
|------|--------|--------|
| **W1** | Built-in catalog (`coursera_specialization`, `coursera_course`, `coursera_module` v**1**); `GET` list/detail (incl. example outline JSON); `POST …/propose` → F1 handoff graph + summary; `POST …/apply` → transactional create + **`template_apply`** receipt; receipt lookup by idempotency key; mapper reuse from Theme F outline packs | **Quality green** — **14** pytest (`test_f5_w1_templates.py`) |
| **W2** | CLI **`theplan templates`** list/get/propose/apply/receipt (same API; `--attach-kind` / `--attach-id`, `--skip-optional`, `--idempotency-key`) | **Landed** (working tree) · operator manual **Open** |
| **W3** | Web: **`ImportPanel`** shell — **Templates** tab → **`TemplatesPanel`** (`/templates/*`); **Custom outline** tab → **`OutlineImportPanel`** (`/outlines/*`); scaffold banners; example JSON / form paths | **Implemented** — web build green (**2026-10-10**) · **IM-R1 Dex verified closed** · PARTIAL operator rows **Open** |
| **F5-B expand** | Optional-item toggle parity, supplied titles/URLs/labels, duration estimate disclosure in propose/review UX | **Quality green** — **7** pytest (`test_f5_b_templates.py`) + W1 partial; CLI list/get + IBM **417** apply (Renee) · operator manual **Open** |
| **B-F5-1** | Outline ↔ Templates **panel merge** (product) | **Dex verified closed (2026-10-10)** — single Import modal + tabs; **IM-R1** draft retention · Trish Done **2026-10-10**; F5 **not Closed** (PARTIAL operator) |

## Built-in templates (v1)

| ID | Creates | Default attach | Outline pack |
|----|---------|----------------|--------------|
| **`coursera_specialization`** | Epic → course projects → module sections → tasks | Root (new epic) or **`attach_under` epic** (graft courses onto existing epic) | `coursera_specialization` |
| **`coursera_course`** | One project → modules → tasks | Root (standalone project) or **`attach_under` epic** | `coursera_specialization` |
| **`coursera_module`** | One section → tasks (or tasks-only under section) | **`attach_under` project or section** (required) | `coursera_specialization` |

Catalog is **code-defined** ([`builtin_templates.py`](../../apps/api/app/services/builtin_templates.py)) — not a DB template CRUD surface. Updating template **version** in code does **not** rewrite existing projects.

**Scaffold vs syllabus:** Example outlines for course/module (and blank specialization fixture) are intentionally minimal; `GET` detail and propose set **`is_scaffold`** when content still matches the blank pattern, with a propose **warning** to replace titles before apply.

## Scope — acceptance mapping

| Slice | Capability | W1 / later |
|-------|------------|------------|
| **F5-A** | All three shapes; root vs graft attach modes; course standalone vs under epic; module under project vs section (tasks-only) | **W1 (landed):** specialization/course/module pytest matrix; attach validation (`TEMPLATE_ATTACH_*`, `OUTLINE_ATTACH_NOT_FOUND`) |
| **F5-B** | Optional items included by default; `skip_optional` on propose; empty/scaffold outlines; preserve supplied titles, URLs, ordering, task-type labels; estimate disclosure (no invented durations) | **W1 + F5-B (Quality green):** skip_optional, scaffold, labels/durations in **`test_f5_b_templates.py`** (**7**) atop W1 **14**. W3 UX landed (toggle, warnings, scaffold banners). Trish Done **2026-10-10**; PARTIAL operator rows open |
| **F5-C** | Same idempotency key replays one graph/receipt; new key → new instance; duplicate source URL **warns** (no merge); key namespace separate from F1 handoff | **W1 (landed):** replay, second instance, `IDEMPOTENCY_KEY_REUSE`, handoff receipt lookup **404** for template keys |
| **F5-D** | Legacy **`/outlines/propose`** unchanged; IBM RAG golden fixture; template proposer matches legacy summary counts | **W1 (landed):** `test_legacy_outline_fixture_still_proposes`, IBM parity (**417** tasks, **10** projects, **30** sections) |

## F1 handoff integration

Templates are **not** a second persistence engine:

1. **Propose** maps outline JSON → **`HandoffGraphPayload`** (via existing outline mapper + `propose_handoff` defaults/warnings).
2. **Apply** calls the same **`apply_handoff`** path as F1 with:
   - **`operation_kind`:** `template_apply` (F1 uses `handoff_apply`).
   - **Receipt metadata:** `template_id`, `template_version` echoed on apply/receipt JSON.
3. **Apply body:** F1 **`HandoffApplyRequest`** — proposed `payload` fields + **`idempotency_key`** (UUID).
4. **Receipt lookup:** `GET /api/v1/templates/receipts/by-key/{idempotency_key}` only (not `/handoffs/receipts/...`).

Default root **`schedule_policy`** for template graphs is **`manual`** (Theme F parity). Created epic roots get manual style; tasks inherit per F1 rules.

Delivery reference: [F1-HANDOFF.md](./F1-HANDOFF.md) · API: [05-api-contract.md](../05-api-contract.md) § Planning handoff · § Coursera templates.

## Legacy outline ingest (preserved)

Theme F **`POST /api/v1/outlines/propose`** and **`POST /api/v1/outlines/apply`** remain the operator path for **custom outline** import. Packs **`coursera_specialization`** and **`hierarchy_v1`** (same mapper) are unchanged.

| Concern | Outline ingest (Custom outline tab) | F5 `/templates` (Templates tab) |
|---------|-------------------------------------|-----------------------------------|
| **Web entry** | **`ImportPanel`** → **Custom outline** → **`OutlineImportPanel`** | **`ImportPanel`** → **Templates** → **`TemplatesPanel`** |
| **Idempotency** | **None** — re-import duplicates | **Apply** uses F1-style keys + receipts |
| **Apply shape** | Approved action list | Handoff graph from propose |
| **Templates exposed** | `coursera_specialization`, `hierarchy_v1` | Three **Coursera-shaped** builtins (+ graft modes per template) |
| **CLI** | (UI-first prove-it) | **`theplan templates`** (W2) |

Deep links: `?import=templates|outline|custom|template` opens the modal on the matching tab (query stripped after open). Custom event **`theplan:open-import`** with optional mode detail.

Operator docs: [OUTLINE-INGEST.md](../OUTLINE-INGEST.md) · [ADR-011](../adr/ADR-011-templates-outline-ingest.md).

## Integration

| Layer | Contract | W1 / W2 / W3 |
|-------|----------|----------------|
| **API** | `/api/v1/templates` family — [05-api-contract.md](../05-api-contract.md) § Coursera templates | W1 automated |
| **API (legacy)** | `/api/v1/outlines/*` — unchanged; used by Custom outline tab | Theme F preserved |
| **CLI** | `theplan templates list|get|propose|apply|receipt` — [apps/cli/theplan/commands/templates.py](../../apps/cli/theplan/commands/templates.py) | W2 landed; [CLI.md](../CLI.md) **F5 — Coursera templates** section documents command family |
| **Web** | **`ImportPanel.tsx`** — tabbed **Templates** + **Custom outline**; embedded **`TemplatesPanel`** / **`OutlineImportPanel`** | **B-F5-1 Dex verified closed** **2026-10-10**; PARTIAL operator rows **Open** |
| **Auth** | List/get catalog: no session required. Propose/apply/receipt: owner session | Automated on mutating routes |

## Automated evidence

From repo root, API venv active (`apps/api/.venv`):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_f5_w1_templates.py tests/test_f5_b_templates.py -q
```

**Renee (2026-10-09, F5-W1 + F5-B exit):** **21** passed — W1 **14** (catalog, F5-A attach shapes, F5-C idempotency/instances, F5-B partial on W1 file, F5-D legacy + IBM propose parity) + F5-B **7** (labels, durations, duplicate URL warn, optional toggle depth). Apply route persists via explicit **`db.commit()`** after `apply_template`. CLI **`theplan templates list`** / **`get coursera_specialization`** green; IBM specialization **apply** → **417** tasks.

CLI parser smoke (when CLI venv has pytest):

```powershell
cd "F:\Code Repo\ThePlan\apps\cli"
.\.venv\Scripts\python.exe -m pytest tests/test_main_commands.py -q -k templates
```

Web build (includes **ImportPanel** merge):

```powershell
cd "F:\Code Repo\ThePlan\apps\web"
npm run build
```

Apply migrations before live or manual checks (F5 adds no new head):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

Expect head **`027_saved_filter_presentation`** (or at least **`024_time_map_overrides`** for F5-only API).

## Manual checklist (Trish)

Canonical checkboxes: **[MANUAL-CHECKLIST.md](./MANUAL-CHECKLIST.md)** § F5. Do not maintain a second full list here.

## Known limitations (by wave)

| Item | Notes |
|------|-------|
| **Semantic dedupe / merge** | Deferred — duplicate URL warns only |
| **Outline re-import** | Still non-idempotent; template apply idempotency does not change outline behavior |
| **`hierarchy_v1` in `/templates`** | Not a separate catalog id; neutral ingest remains on `/outlines` |
| **F5-B** | Automated + W3 UX green; operator manual rows still **Open** |
| **B-F5-1 Dex** | **IM-R1 verified closed 2026-10-10** — merged Import UX; upload/download and some presentation rows remain **PARTIAL** |
| **Close policy** | Trish Done **2026-10-10**; F5 **not Closed** until PARTIAL operator rows dispositioned |

## Related documents

- Spec §8 — [NEXT-FEATURES-SPEC.md](../NEXT-FEATURES-SPEC.md#8-f5-coursera-templates)
- F1 receipts — [F1-HANDOFF.md](./F1-HANDOFF.md)
- Legacy outline — [OUTLINE-INGEST.md](../OUTLINE-INGEST.md)
- Fixtures — [testdata/outlines/README.md](../../testdata/outlines/README.md)
- Combined scenario **Disrupted week** — [NEXT-FEATURES-SPEC.md §12](../NEXT-FEATURES-SPEC.md#12-implementation-slices-and-verification-handoff)
