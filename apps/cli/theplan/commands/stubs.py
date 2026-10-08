from __future__ import annotations

from theplan.output import emit_error


def not_implemented(feature: str) -> None:
    emit_error(
        code="NOT_IMPLEMENTED",
        message=f"{feature} is not implemented in M1; planned for M2",
        exit_code=1,
    )
