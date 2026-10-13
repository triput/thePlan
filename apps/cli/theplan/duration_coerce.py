"""Pass plain minute integers as JSON numbers; keep friendly strings as strings."""

from __future__ import annotations

import re

_PLAIN_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def duration_json_value(raw: str) -> int | str:
    text = " ".join(raw.strip().split())
    if _PLAIN_NUMBER.fullmatch(text) and "." not in text:
        return int(text)
    return text
