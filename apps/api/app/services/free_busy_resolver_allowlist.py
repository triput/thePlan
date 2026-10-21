"""Fail-closed resolver allowlist (T1-4a §1)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

_logger = logging.getLogger(__name__)


def parse_resolver_allowlist_file(path: str | None) -> frozenset[str]:
    """Read UTF-8 allowlist; invalid line ⇒ empty set (deny all)."""
    if not path or not str(path).strip():
        return frozenset()
    file_path = Path(path)
    if not file_path.is_file():
        _logger.warning("resolver allowlist missing or unreadable: %s", path)
        return frozenset()
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        _logger.warning("resolver allowlist read failed: %s", path)
        return frozenset()
    allowed: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        comment = stripped.find("#")
        if comment >= 0:
            stripped = stripped[:comment].strip()
            if not stripped:
                continue
        try:
            parsed = uuid.UUID(stripped)
        except ValueError:
            _logger.warning(
                "resolver allowlist invalid UUID at line %s in %s",
                line_no,
                path,
            )
            return frozenset()
        allowed.add(str(parsed).lower())
    return frozenset(allowed)


def user_may_resolve(user_id: uuid.UUID, allowlist_path: str | None) -> bool:
    parsed = parse_resolver_allowlist_file(allowlist_path)
    if not parsed:
        return False
    return str(user_id).lower() in parsed
