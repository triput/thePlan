"""Save/wrap/restore covering_release_plan.CoveringHTTP for fixture transport injection."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import app.services.covering_release_plan as release_plan
from app.services.covering_http_transport import CoveringHTTP


class CoveringHTTPAliasError(RuntimeError):
    pass


class _AliasState:
    original = None
    wrapped = False


def install_covering_http_alias(*, transport_factory):
    """Replace module CoveringHTTP with a wrapper that injects transport_factory."""
    if _AliasState.wrapped:
        raise CoveringHTTPAliasError("CoveringHTTP alias already wrapped")
    original = release_plan.CoveringHTTP
    if getattr(original, "__name__", "") not in ("CoveringHTTP", "wrapped_for_plan"):
        # Accept the real class object even when imported under alias.
        if original is not CoveringHTTP and not callable(original):
            raise CoveringHTTPAliasError("unexpected CoveringHTTP alias target")

    def wrapped_for_plan(*, counter, routes):
        # for_request omits transport_factory; inject fixture byte transport here.
        return CoveringHTTP(counter=counter, routes=routes, transport_factory=transport_factory)

    _AliasState.original = original
    release_plan.CoveringHTTP = wrapped_for_plan  # type: ignore[assignment]
    _AliasState.wrapped = True
    return original


def restore_covering_http_alias() -> None:
    if not _AliasState.wrapped:
        return
    if _AliasState.original is None:
        raise CoveringHTTPAliasError("missing original CoveringHTTP")
    release_plan.CoveringHTTP = _AliasState.original  # type: ignore[assignment]
    _AliasState.original = None
    _AliasState.wrapped = False


def alias_is_wrapped() -> bool:
    return _AliasState.wrapped


@contextmanager
def covering_http_alias(*, transport_factory) -> Iterator[None]:
    install_covering_http_alias(transport_factory=transport_factory)
    try:
        yield
    finally:
        restore_covering_http_alias()
