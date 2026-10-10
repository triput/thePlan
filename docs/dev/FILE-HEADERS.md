# File headers (module info blocks)

Operator-preferred **banner header** at the top of non-trivial source files and delivery docs. Short purpose + identity fields — not a novel, not a changelog.

**Preferred:** the block below (comment syntax varies by language). Keep Description to one sentence.

---

## Canonical shape

```
==============================================================================
//  File: path/relative/to/repo.ext
//  Description: One-sentence purpose.
//  Component: Area name
//  Version: 1.0
//  Created: YYYY-MM-DD
//  Last Update: YYYY-MM-DD
// ==============================================================================
```

Use `(Gold Master)` on Version only when that artifact is frozen/shipped; omit for in-progress wave code.

---

## Python (`apps/api`, `apps/cli`)

Module docstring **or** `#` banner as the first content (before `from __future__` if using a docstring — PEP 236). Prefer the `#` banner so fields stay machine-scannable:

```python
# ==============================================================================
#  File: apps/api/app/services/example.py
#  Description: One-sentence purpose.
#  Component: Saved Views
#  Version: 1.0
#  Created: 2026-10-10
#  Last Update: 2026-10-10
# ==============================================================================

from __future__ import annotations
```

Optional second purpose line may live in a short module docstring *below* the banner if ADR/layer notes help.

---

## TypeScript / TSX (`apps/web`)

```tsx
// ==============================================================================
//  File: apps/web/src/example.ts
//  Description: One-sentence purpose.
//  Component: Saved Views
//  Version: 1.0
//  Created: 2026-10-10
//  Last Update: 2026-10-10
// ==============================================================================
```

`api.ts` and similar multi-section clients can stay lighter (section comments inside); banners on entry surfaces and fat modules.

---

## Markdown (delivery / guides)

HTML comment banner immediately under the `#` title (or as the first lines):

```markdown
# Title

<!--
==============================================================================
  File: docs/delivery/EXAMPLE.md
  Description: One-sentence purpose.
  Component: Docs/Delivery
  Version: 1.0
  Created: 2026-10-10
  Last Update: 2026-10-10
==============================================================================
-->
```

Bold **File** / **Status** lines below the title remain fine for human scanning; do not duplicate contradictory dates.

---

## Do **not** require headers on

- Tiny pure re-export barrels
- Generated code
- Trivial one-liner helpers
- Test fixtures that are data-only
- `__pycache__` / build output

When in doubt: if you’d open the file to learn *why it exists*, give it a header.

---

## Rollout

Convention updated **2026-10-10** to match the operator banner format. Wave F4/F6/F7 modules are the apply set; broader backlog remains **[DEF-013](../DEFECTS.md#def-013--file-headers-across-apiweb-hotspots)**.
