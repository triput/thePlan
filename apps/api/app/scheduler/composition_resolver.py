"""Seam from collect / live snapshot reads to Jules's assignment resolver.

Jules owns the stored assignment rows. This module does not query them. When
``app.scheduler.new_rule_resolver.resolve_new_rule_compositions`` (or
``app.scheduler.assignment_resolver`` with the same symbol) exists, collect and
``live_snapshots_by_task`` both call it and then
``resolve_effective_composition``, so the fingerprint and the placer see one
resolved rule set.

Expected signature::

    def resolve_new_rule_compositions(db, owner_id, tasks, projects, epics) -> dict

Values are :class:`CompositionInput` or the dict shape accepted by
``composition_input_from_mapping``. Omit tasks with no assignment. Return
``family="legacy"`` for an unconverted map that won the cross-level resolution
so the placer does not compose onto it. Return ``family="conflict"`` when both
families are active at one scope — the placer refuses rather than picking one.

Until that module is on the branch, every task stays on the V3 path.
"""

from __future__ import annotations

import importlib
from typing import Any
from uuid import UUID

from app.scheduler.composition import (
    CompositionInput,
    EffectiveComposition,
    coerce_composition_input,
    resolve_effective_composition,
)

_RESOLVER_MODULES = (
    "app.scheduler.assignment_resolver",
    "app.scheduler.new_rule_resolver",
)
_RESOLVER_SYMBOL = "resolve_new_rule_compositions"


def _resolver():
    for module_name in _RESOLVER_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        fn = getattr(module, _RESOLVER_SYMBOL, None)
        if fn is not None:
            return fn
    return None


def load_compositions_by_task(
    db: Any,
    owner_id: UUID,
    tasks: list[Any],
    projects: dict[UUID, Any],
    epics: dict[UUID, Any],
) -> dict[UUID, CompositionInput]:
    """Raw resolver payload. Empty when Jules has not landed the symbol."""
    if not tasks:
        return {}
    fn = _resolver()
    if fn is None:
        return {}
    raw = fn(db, owner_id, tasks, projects, epics) or {}
    coerced: dict[UUID, CompositionInput] = {}
    for task_id, value in raw.items():
        coerced[UUID(str(task_id))] = coerce_composition_input(value)
    return coerced


def load_effective_compositions(
    db: Any,
    owner_id: UUID,
    tasks: list[Any],
    projects: dict[UUID, Any],
    epics: dict[UUID, Any],
) -> dict[UUID, EffectiveComposition]:
    """Same resolved rules for placement and for the collected snapshot."""
    raw = load_compositions_by_task(db, owner_id, tasks, projects, epics)
    return {
        task_id: resolve_effective_composition(item)
        for task_id, item in raw.items()
    }
