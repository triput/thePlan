"""DEF-030: task patch must include --title in the API payload."""

from __future__ import annotations

import argparse

import pytest

from theplan.commands.tasks import _optional_task_fields
from theplan.errors import CliError


def _ns(**kwargs: object) -> argparse.Namespace:
    defaults = {
        "title": None,
        "project_id": None,
        "due_at": None,
        "priority": None,
        "estimated_duration_minutes": None,
        "remaining_estimate_minutes": None,
        "expected_revision": None,
        "description": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_patch_title_only_sends_title() -> None:
    body = _optional_task_fields(_ns(title="  Lab: Restored  "), for_create=False)
    assert body == {"title": "Lab: Restored"}


def test_patch_title_with_description_sends_both() -> None:
    body = _optional_task_fields(
        _ns(title="Lab: Restored", description="notes"),
        for_create=False,
    )
    assert body == {"title": "Lab: Restored", "description": "notes"}


def test_patch_empty_still_errors() -> None:
    with pytest.raises(CliError) as exc:
        _optional_task_fields(_ns(), for_create=False)
    assert exc.value.code == "INVALID_USAGE"


def test_patch_expected_revision_alone_is_not_a_patch() -> None:
    with pytest.raises(CliError) as exc:
        _optional_task_fields(_ns(expected_revision=4), for_create=False)
    assert exc.value.code == "INVALID_USAGE"
    assert "remaining-estimate-minutes" in exc.value.message


def test_patch_title_drops_revision_token_without_remaining() -> None:
    body = _optional_task_fields(
        _ns(title="Lab", expected_revision=4),
        for_create=False,
    )
    assert body == {"title": "Lab"}
