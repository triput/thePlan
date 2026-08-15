# File headers (module info blocks)

Short purpose headers at the top of non-trivial source files. Quirk the operator wants as convention — not a novel, not a wall of metadata.

**Preferred length:** 2–6 lines. One sentence can be enough when the name already says it.

---

## Python (`apps/api`)

Put a **module docstring** as the **first statement**, then `from __future__` if used (PEP 236 — docstring must precede future imports so `__doc__` is set).

```python
"""One-line purpose.

Optional second line: ADR / theme refs; ownership layer (route | service | model | scheduler).
"""

from __future__ import annotations
```

### Include when useful

| Field | Notes |
|-------|--------|
| **Purpose** | What this module owns (not a function inventory) |
| **ADR / theme** | e.g. ADR-010, Theme F — only when relevant |
| **Layer** | `route` · `service` · `model` · `scheduler` (or `api deps`) |

Skip class/function Gold Master banners. No author/date/changelog in the header.

### Good examples (in-tree)

```python
"""OpenAI-compatible chat client for Assist (default: Ollama). ADR-010.

Service layer — propose JSON actions from natural language.
"""
```

```python
"""Merge external calendar busy + pinned blocks into sorted BUSY intervals.

Scheduler layer — input to fuzzy placement / replan (ADR-005, ADR-006).
"""
```

---

## TypeScript / TSX (`apps/web`)

Use a brief top file comment for **non-trivial** modules — entry surfaces, fat panels, hooks that own a pipeline:

```tsx
/**
 * Outline import UI — propose → review → apply (Theme F / ADR-011).
 * Entry surface for Coursera specialization pack ingest.
 */
```

`api.ts` and similar multi-section clients can stay **lighter** (section comments inside the file are fine; no need for a six-line banner on every helper).

Prefer `/** ... */` over `//` stacks so it reads as a file info block.

---

## Do **not** require headers on

- Tiny pure re-export barrels (`index.ts` that only re-exports)
- Generated code
- Trivial one-liner helpers with an obvious name and no cross-cutting role
- Test fixtures that are data-only

When in doubt: if you’d open the file to learn *why it exists*, give it a header.

---

## Rollout

Convention established here. Broad apply across api/web hotspots is tracked as **[DEF-013](../DEFECTS.md#def-013--file-headers-across-apiweb-hotspots)**. Starter headers land with this doc so the rule isn’t vaporware.
