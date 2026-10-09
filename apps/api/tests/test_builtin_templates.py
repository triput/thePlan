"""Packaged template examples and blank-scaffold detection. No database."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import builtin_templates as bt

_API_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKAGED = _API_ROOT / "app" / "data" / "outlines" / "blank_hierarchy_v1.json"
_SOURCE = _REPO_ROOT / "testdata" / "outlines" / "blank_hierarchy_v1.json"
_IBM = (
    _REPO_ROOT
    / "testdata/outlines/ibm_rag_agentic_ai_professional_certificate_curriculum.json"
)


def test_example_outline_for_reads_package_data_without_testdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production image has no /testdata mount. _repo_root() is None there."""
    monkeypatch.setattr(bt, "_repo_root", lambda: None)
    outline = bt.example_outline_for("coursera_specialization")
    assert outline["certificate"]["title"].startswith("Your program")
    assert outline["courses"][0]["modules"]

    course = bt.example_outline_for("coursera_course")
    assert course["course"]["title"].startswith("First course")
    module = bt.example_outline_for("coursera_module")
    assert module["module"]["tasks"]

    path = bt._package_outline_path("blank_hierarchy_v1.json")
    app_dir = Path(bt.__file__).resolve().parents[1]
    assert path.is_file()
    assert path.is_relative_to(app_dir / "data" / "outlines")
    assert "testdata" not in path.parts


def test_dockerfile_copy_includes_packaged_outline() -> None:
    dockerfile = (_API_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY . ." in dockerfile
    assert _PACKAGED.is_file()
    assert _PACKAGED.is_relative_to(_API_ROOT)
    ignore = (_API_ROOT / ".dockerignore").read_text(encoding="utf-8")
    blocked = {
        line.strip()
        for line in ignore.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "*.json" not in blocked
    assert "app/data" not in blocked
    assert "app/data/**" not in blocked


def test_packaged_outline_matches_testdata_source() -> None:
    assert json.loads(_PACKAGED.read_text(encoding="utf-8")) == json.loads(
        _SOURCE.read_text(encoding="utf-8")
    )


def test_renamed_course_with_sample_tasks_stays_scaffold() -> None:
    outline = bt.example_outline_for("coursera_course")
    outline["course"]["title"] = "My statistics course"
    outline["course"]["url"] = "https://www.coursera.org/learn/basic-statistics"
    assert bt.is_blank_scaffold(outline, "coursera_course") is True


def test_renamed_course_with_cleaned_task_titles_stays_scaffold() -> None:
    outline = bt.example_outline_for("coursera_course")
    outline["course"]["title"] = "My statistics course"
    outline["course"]["url"] = "https://www.coursera.org/learn/basic-statistics"
    outline["course"]["modules"] = [
        {
            "module_order": 1,
            "title": "Week 9 — Something else",
            "tasks": [
                {"title": "Welcome and overview", "task_type": "video"},
                {"title": "Real reading", "task_type": "reading"},
            ],
        }
    ]
    assert bt.is_blank_scaffold(outline, "coursera_course") is True


def test_replaced_course_structure_is_not_scaffold() -> None:
    outline = bt.example_outline_for("coursera_course")
    outline["course"]["title"] = "My statistics course"
    outline["course"]["url"] = "https://www.coursera.org/learn/basic-statistics"
    for module in outline["course"]["modules"]:
        module["title"] = f"Inference {module['module_order']}"
        for task in module["tasks"]:
            task["title"] = f"Work through problem set {task['task_order']}"
    assert bt.is_blank_scaffold(outline, "coursera_course") is False


def test_renamed_specialization_and_module_keep_scaffold_flag() -> None:
    spec = bt.example_outline_for("coursera_specialization")
    spec["certificate"]["title"] = "Statistics certificate"
    spec["certificate"]["source_url"] = "https://www.coursera.org/professional-certificates/stats"
    assert bt.is_blank_scaffold(spec, "coursera_specialization") is True

    module = bt.example_outline_for("coursera_module")
    module["module"]["title"] = "Inference"
    assert bt.is_blank_scaffold(module, "coursera_module") is True


def test_ibm_curriculum_is_not_blank_scaffold() -> None:
    outline = json.loads(_IBM.read_text(encoding="utf-8"))
    assert bt.is_blank_scaffold(outline, "coursera_specialization") is False
