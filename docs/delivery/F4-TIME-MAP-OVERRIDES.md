# F4 — Temporary Time Map overrides

**Latest Dex gate, 2026-10-10:** F4 Wave 1 **verified closed** — CLI overrides CRUD, day overlay, F4-D red/pins/legend/small-run stale, and **W1-R1** volume stale badge via **`GET /api/v1/schedule/runs/{run_id}/stale-summary`** + **`CalendarView`** ([DEX-WAVE1-RETEST](./DEX-WAVE1-RETEST-2026-10-10.md), [DEX-IMPORT-VOLUME](./DEX-IMPORT-VOLUME-2026-10-10.md)). F6 R1 verified closed (**37** API integration tests incl. concurrent reparent). Web **36** + CLI **36** tests green. Trish Done sign-off **2026-10-10** ([sign-off table](./MANUAL-CHECKLIST.md#sign-off)); F4 **not Closed** (optional DST).

**Status:** W1 spine **Implemented** · **Quality:** F4-W1 API pytest **17** green (**2026-10-09**, Renee exit) · **W2 Implemented** · **Quality (W2):** F4-W2 pytest **22** green (**2026-10-09**, Renee exit) · **W3 Implemented (2026-10-10)** — Settings Overrides CRUD + **week** overlay **Dex-verified (Trish/Dex, 2026-10-09)**; **CLI** `theplan overrides` list/get/create/edit/delete **Dex-verified**; **day-mode** override overlay + **F4-D** red/stale/legend **Dex-verified** (`npm run build` green) · push **not requested** · F4 **Open / in-progress** — **not** Closed/shipped (Trish Done **2026-10-10**; optional DST browser spot-check open; **not Closed**)

**Spec:** [NEXT-FEATURES-SPEC.md §7](../NEXT-FEATURES-SPEC.md#7-f4-temporary-time-map-overrides)  
**Build:** working tree on `cursor` `main` (includes uncommitted **F4-W3** web UI; prior documented tip **`cc87349`** was W1-only; **no push** this pass)  
**Hygiene:** Alembic head **`024_time_map_overrides`** (after F3 **`023_schedule_outcome_provenance`**)

## Wave map

| Wave | Scope | Status |
|------|--------|--------|
| **W1** | Migration + nested override CRUD; overlap/timezone/range validation on write; scheduler **collect** loads horizon-intersecting overrides; **placement** resolves per-day effective bands; **`placement_facts.applicable_override`** on replan; no auto-replan on override write | **Quality green** — 17 pytest (API + scheduler) |
| **W2** | Snapshot **v3** (placement stays **`f3-w2`**): **`time_map_overrides`** in fingerprint + stale compare; override create/patch/delete marks **`time_map_overrides`** stale on read (**no** auto-replan); **DST placement** suite; **F4-B** inherited map + **cross-map independence** acceptance | **Quality green** — **22** pytest (`test_f4_w2_scheduler.py` + extended `test_input_fingerprint.py`) |
| **W3** | **Web:** Settings Overrides CRUD; **week** + **day** calendar override overlay; **F4-D** red/stale/legend UI slice. **CLI:** `theplan overrides` CRUD. Prior week Settings/overlay **Dex-verified (2026-10-09)**; Wave 1 CLI/day/F4-D **Dex-verified (2026-10-10)** incl. **W1-R1** volume stale | **Implemented** · Trish Done **2026-10-10** · F4 **not Closed** (optional DST) |

## Scope — acceptance mapping

| Slice | Capability | W1 / later |
|-------|------------|------------|
| **F4-A** | One-day and multi-day inclusive ranges; base weekly map unchanged outside range; expired rows stay listed; scheduler uses base again after range | **W1 (landed):** CRUD preserves base map bands; inclusive multiday placement; resolver date-order; replan multiday inside / base outside; expired listed + horizon load + base placement |
| **F4-B** | Resolve task’s **inherited** map first; override on map A does not constrain map B; unbound task has no override | **W2 (landed):** inherit chain + cross-map isolation in `test_f4_w2_scheduler.py` |
| **F4-C** | Stored IANA timezone on override; reject overlapping ranges on same map; local date boundaries; DST-safe derivation; reject midnight-crossing bands | **W1 (partial):** overlap 409 (`TIME_MAP_OVERRIDE_OVERLAP`), adjacent/other-map OK, midnight/tz/range 422, user timezone change does not rewrite stored bounds, horizon resolve uses stored timezone. **W2 (landed):** **DST placement** pytest suite |
| **F4-D** | All-day unavailability, non-working days, red precedence within effective map, pins/external busy unchanged, stale schedule indicators after override edits | **W1 (partial):** empty strict bands → all-day unavailable (API). **W3:** week + day overlay; red/stale/legend + full-run stale banner — **Dex verified closed 2026-10-10** (**W1-R1** volume case) |

**Also in W1 slice:** `time_map_overrides` + `time_map_override_bands` — [04-data-schema.md](../04-data-schema.md); scheduler module notes — [apps/api/app/scheduler/README.md](../../apps/api/app/scheduler/README.md).

## Scheduler behavior (W1)

1. **`collect`** loads override rows (and bands) intersecting the replan horizon, keyed by map id.
2. **`placement`** picks the override for each scheduling local day in the override’s stored timezone; outside inclusive dates the base map bands apply.
3. **`placement_facts.applicable_override`** on outcomes records override id, stored local bounds, and effective local date when an override governed that day.

**W2:** New replans persist snapshot **v3**; stale compare includes **`time_map_overrides`** on the task's effective map. Override **create / patch / delete** updates live override data so explanation GETs can show **`time_map_overrides`** in **`stale_categories`** without starting replan ([F3 delivery](./F3-SCHEDULER-EXPLANATIONS.md), [05-api-contract.md](../05-api-contract.md) § Schedule · Time Map overrides).

## Integration

| Layer | Contract | W1 |
|-------|----------|-----|
| **API** | `GET/POST /focus-windows/{id}/overrides`, `GET/PATCH/DELETE …/{override_id}` — [05-api-contract.md](../05-api-contract.md) § Time Map overrides | Automated CRUD + validation |
| **Scheduler** | Overrides in collect → placement; `applicable_override` on replan | Automated placement + replan facts |
| **CLI** | Override list/create/edit/delete commands | **W3 landed (2026-10-10):** `theplan overrides` — maps to `/api/v1/focus-windows/{map_id}/overrides`; CLI tests green — [CLI.md](../CLI.md) |
| **Web** | Settings Overrides CRUD; week + day Time Map overlay + F4-D chrome | **W3:** Settings/week **Dex-verified 2026-10-09**; day overlay + F4-D **Dex-verified 2026-10-10** (`npm run build` green); Trish Done **2026-10-10**; **not Closed** |
| **Auth** | Owner-scoped; foreign window/override → **404** | Automated |

## Automated evidence

From repo root, API venv active (`apps/api/.venv`):

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_f4_w1_scheduler_overrides.py tests/test_time_map_override_api.py -q
```

**Renee (2026-10-09, F4-W1 exit):** **17** passed — `test_f4_w1_scheduler_overrides.py` (scheduler + F4-A replan/placement) + `test_time_map_override_api.py` (nested CRUD + F4-C validation).

**Renee (2026-10-09, F4-W2 exit):** **22** passed — `test_f4_w2_scheduler.py` + extended `test_input_fingerprint.py` (expanded from **17** W1-only baseline).

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\python.exe -m pytest tests/test_f4_w2_scheduler.py tests/test_input_fingerprint.py -q
```

Covers snapshot **v3**, override stale on CRUD, DST local-date → UTC placement, F4-B inherit + cross-map isolation.

Apply migrations before live or manual checks:

```powershell
cd "F:\Code Repo\ThePlan\apps\api"
.\.venv\Scripts\alembic.exe upgrade head
```

Expect head **`024_time_map_overrides`**.

## Manual checklist (Trish)

Canonical checkboxes: **[MANUAL-CHECKLIST.md](./MANUAL-CHECKLIST.md)** § F4. Do not maintain a second full list here.

## Known limitations (by wave)

| Item | Notes |
|------|-------|
| **Stale / fingerprint** | **W2 landed:** v3 compare includes **`time_map_overrides`**; override CRUD marks stale on read. Legacy v2 explanation rows still **`provenance`** until replan. **`priority_ups`** still not compared |
| **F4-B** | **W2 landed (Quality green):** inherit + cross-map in pytest; operator manual still open |
| **F4-C DST** | **W2 landed (Quality green):** placement DST matrix in pytest; operator spot-check optional |
| **F4-D** | Red/pins/legend + small-run and **volume** stale badge **Dex verified closed 2026-10-10** (**W1-R1** / **`stale-summary`**) |
| **W3 day overlay** | Day view paints effective override bands — **Dex verified closed 2026-10-10** |
| **W3 CLI** | **`theplan overrides`** list/get/create/edit/delete — CLI tests green; operator Dex CRUD **verified closed 2026-10-10** |
| **F3 overlap** | Fuller override provenance in explanations may deepen in F4 W2–W3; F3-W2 **`placement_facts`** already expose **`applicable_override`** when present |
| **Close policy** | F4 stays **Open / in-progress** until W3/CLI/F4-D, manual sign-off, and delivery policy — **not** Closed/shipped on W1/W2 Quality alone |

## Related documents

- Data: `time_map_overrides`, `time_map_override_bands` — [04-data-schema.md](../04-data-schema.md)
- Explanations + deferred stale field — [F3-SCHEDULER-EXPLANATIONS.md](./F3-SCHEDULER-EXPLANATIONS.md)
- Combined scenario **Disrupted week** — [NEXT-FEATURES-SPEC.md §12](../NEXT-FEATURES-SPEC.md#12-implementation-slices-and-verification-handoff)
