"""Disposable Microsoft primary alias canonicalization seed.

PREPARED ONLY. Alias → canonical calendar ID seed for live identity evidence observation.
Does not mutate production route tables.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class AliasSeed:
    case_id: str
    provider: str
    alias_label: str
    canonical_calendar_id_label: str
    seed_hash: str


def microsoft_primary_alias_seed(*, case_id: str) -> AliasSeed:
    if not case_id.startswith("NP-"):
        raise RuntimeError("case_id refused")
    alias_label = f"fixture-ms-primary-alias:{case_id}"
    canonical_label = f"fixture-ms-canonical-calendar:{case_id}"
    digest = hashlib.sha256(f"{alias_label}|{canonical_label}".encode("utf-8")).hexdigest().upper()
    return AliasSeed(
        case_id=case_id,
        provider="microsoft",
        alias_label=alias_label,
        canonical_calendar_id_label=canonical_label,
        seed_hash=digest,
    )


def sanitized_alias_receipt(seed: AliasSeed) -> dict[str, str]:
    return {
        "case_id": seed.case_id,
        "provider": seed.provider,
        "alias_label_present": "true",
        "canonical_label_present": "true",
        "seed_hash": seed.seed_hash,
        "live_calendar_id": "false",
    }


if __name__ == "__main__":
    raise SystemExit("HELD: np_alias_seed preparation only; no DB writes")
