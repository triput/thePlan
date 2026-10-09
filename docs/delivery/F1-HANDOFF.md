# F1 — CLI planning handoff

**Status:** Implemented · **Quality:** Renee exit **2026-10-08** (automated green) · **Manual verification:** pending (Trish)  
**Spec:** [NEXT-FEATURES-SPEC.md §4](../NEXT-FEATURES-SPEC.md#4-f1-cli-planning-handoff)  
**Build:** WIP — commit hash pending parent wave commit  
**Hygiene:** [HYGIENE-R4-QUICKSCAN.md](../HYGIENE-R4-QUICKSCAN.md) (pass; Alembic head **019**)

## Scope

| Slice | Capability | Automated |
|-------|------------|-----------|
| **F1-A** | Graph creates project, sections, nested tasks, dependencies; `source_refs` on root read back | `test_f1_a_graph_create_and_readback` |
| **F1-B** | Same idempotency key replays one graph / one receipt; unique-key race returns same receipt | `test_f1_b_idempotent_replay`, `test_f1_b_concurrent_unique_key_one_receipt` |
| **F1-C** | Invalid parent, cycle, or payload/key conflict → no partial writes | `test_f1_c_*` |
| **F1-D** | Task graft leaves host parent `schedule_style`; manual tasks excluded from replan candidates; inherited policy honored | `test_f1_d_*`, `test_inherited_schedule_policy_on_handoff` |
| **F1-E** | Propose discloses duration + priority defaults; omitted dates stay absent on apply | `test_handoff_propose_discloses_defaults`, `test_f1_e_propose_discloses_priority_and_omits_due` |

**Also in slice:** Alembic **`019_handoff_receipts`** (`handoff_receipts` + `source_refs` on epics/projects); task dependency API + CLI; epic/project/section CLI CRUD; task complete/uncomplete CLI.

**Not F1:** Outline ingest remains a separate propose/apply path and is still **non-idempotent** on re-import — [OUTLINE-INGEST.md](../OUTLINE-INGEST.md). Closeout P2 scheduling fixes shipped with this wave; [DEF-028](../DEFECTS.md#def-028--calendar-mirror-delete-failure-recovery-pending-deletion) (mirror delete recovery) stays deferred.

## Integration

| Layer | Contract |
|-------|----------|
| **API** | `POST /api/v1/handoffs/propose`, `POST /api/v1/handoffs/apply`, receipt lookup under `/api/v1/handoffs/receipts/...`; task deps under `/api/v1/tasks/{id}/dependencies` — [05-api-contract.md](../05-api-contract.md) |
| **CLI** | `handoff`, `epics` / `projects` / `sections`, `tasks complete|uncomplete`, `deps` — [CLI.md](../CLI.md), [apps/cli/README.md](../../apps/cli/README.md) |
| **Auth** | Owner-scoped session; same write boundary as other domain routes |
| **Idempotency** | Owner + `handoff_apply` kind + UUID key; same canonical payload replays; different payload → **409** `IDEMPOTENCY_KEY_REUSE` |

## Automated evidence

From repo root, with API venv active (`apps/api/.venv`):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_handoffs.py -q
```

**Renee quality exit (2026-10-08):** `tests/test_handoffs.py` **12** passed; adjacent API (outlines + soft-delete + scheduler deps) **38** passed before the two added F1-B/F1-E cases; CLI **33** passed.

Adjacent API (hierarchy, complete, dependency edges exercised with handoff suite):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_handoffs.py tests/test_sections.py tests/test_task_complete.py tests/test_task_nesting.py tests/test_schedule_style_inherit.py tests/test_scheduler_dependencies.py -q
```

CLI parser + client contract:

```powershell
cd "F:\Code Repo\ThePlan\apps\cli"
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

Apply migration before live or manual CLI checks:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

## Manual checklist (Trish)

- [ ] `theplan auth login` against Compose API; `theplan handoff propose --file …` then `--format text` tree matches JSON entities
- [ ] Apply with a fresh UUID key; `theplan handoff receipt --idempotency-key …` matches apply JSON; second apply shows `replayed: true`
- [ ] Epic or project detail in web UI shows **source refs** after a handoff that included `source_refs`
- [ ] Graft tasks under an existing section: host project schedule style unchanged; new tasks respect handoff `schedule_policy`
- [ ] `theplan deps list|add|remove` round-trip against two real task IDs
- [ ] `theplan epics|projects|sections` list/get/create/patch against owned entities
- [ ] Confirm outline re-import still duplicates (handoff idempotency does **not** apply to outline)

## Known limitations

| Item | Notes |
|------|-------|
| **F1-B concurrent HTTP** | Service-level unique-key race + sequential replay covered; two live HTTP threads against TestClient are not in suite (session not thread-safe) — manual double-apply still useful |
| **F1-E live CLI** | Priority/duration disclosure and omitted dates covered in API tests; end-to-end authenticated CLI round-trip remains on the manual checklist |
| **Outline vs handoff** | Do not use outline apply for agreed-plan idempotency; use `handoff apply` + receipt key |
| **Receipt retention** | Receipts retained for this release; deleting created entities does not allow replay to recreate them (per spec) |
| **DEF-028** | Calendar mirror delete failure recovery — deferred; unrelated to handoff writes |
