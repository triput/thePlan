"""Availability policy slug normalization and validation."""

from __future__ import annotations

import re

from app.models.enums import AvailabilityPolicySlug

SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

RESERVED_AVAILABILITY_POLICY_SLUGS: frozenset[str] = frozenset(
    member.value for member in AvailabilityPolicySlug
)


def policy_slug_str(slug: str | AvailabilityPolicySlug) -> str:
    if isinstance(slug, AvailabilityPolicySlug):
        return slug.value
    return str(slug)


def normalize_custom_policy_slug(raw: str) -> str:
    slug = raw.strip().lower()
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            "slug must start with a letter and contain only lowercase letters, digits, and underscores"
        )
    return slug


def is_builtin_policy_slug(slug: str) -> bool:
    return slug in RESERVED_AVAILABILITY_POLICY_SLUGS
