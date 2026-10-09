"""F5 built-in Coursera template catalog — versioned definitions, no DB catalog."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

TemplateId = Literal["coursera_specialization", "coursera_course", "coursera_module"]

TEMPLATE_VERSION = 1

AttachMode = Literal["root", "epic", "project", "section"]


@dataclass(frozen=True)
class BuiltinTemplate:
    id: TemplateId
    version: int
    title: str
    description: str
    outline_pack: str
    attach_modes: tuple[AttachMode, ...]
    is_scaffold: bool = False


def _package_outline_path(name: str) -> Path:
    """Example JSON lives in the API package so the image needs no testdata mount."""
    return Path(__file__).resolve().parents[1] / "data" / "outlines" / name


def _repo_root() -> Path | None:
    """Dev checkout when this file is under apps/api. None inside the API image."""
    api_root = Path(__file__).resolve().parents[2]
    if api_root.parent.name == "apps":
        return api_root.parents[1]
    return None


def _load_json(name: str) -> dict[str, Any]:
    packaged = _package_outline_path(name)
    if packaged.is_file():
        return json.loads(packaged.read_text(encoding="utf-8"))
    root = _repo_root()
    if root is not None:
        fallback = root / "testdata" / "outlines" / name
        if fallback.is_file():
            return json.loads(fallback.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Outline example {name} is not packaged at {packaged}")


def _course_scaffold() -> dict[str, Any]:
    blank = _load_json("blank_hierarchy_v1.json")
    courses = blank.get("courses") or []
    if not courses:
        return {"course": {"course_order": 1, "title": "Course title", "modules": []}}
    return {"course": courses[0]}


def _module_scaffold() -> dict[str, Any]:
    course = _course_scaffold().get("course") or {}
    modules = course.get("modules") or []
    if not modules:
        return {"module": {"module_order": 1, "title": "Module title", "tasks": []}}
    return {"module": modules[0]}


_BUILTIN: dict[str, BuiltinTemplate] = {
    "coursera_specialization": BuiltinTemplate(
        id="coursera_specialization",
        version=TEMPLATE_VERSION,
        title="Coursera specialization or certificate",
        description="Epic with course projects, module sections, and supplied tasks.",
        outline_pack="coursera_specialization",
        attach_modes=("root", "epic"),
    ),
    "coursera_course": BuiltinTemplate(
        id="coursera_course",
        version=TEMPLATE_VERSION,
        title="Coursera course",
        description="One project with module sections and tasks; standalone or under an existing epic.",
        outline_pack="coursera_specialization",
        attach_modes=("root", "epic"),
    ),
    "coursera_module": BuiltinTemplate(
        id="coursera_module",
        version=TEMPLATE_VERSION,
        title="Coursera course module",
        description="One section with tasks under an existing project (or tasks only under a section).",
        outline_pack="coursera_specialization",
        attach_modes=("project", "section"),
    ),
}


def list_templates() -> list[BuiltinTemplate]:
    return list(_BUILTIN.values())


def get_template(template_id: str) -> BuiltinTemplate | None:
    return _BUILTIN.get(template_id)


def example_outline_for(template_id: str) -> dict[str, Any]:
    if template_id == "coursera_specialization":
        return _load_json("blank_hierarchy_v1.json")
    if template_id == "coursera_course":
        return _course_scaffold()
    if template_id == "coursera_module":
        return _module_scaffold()
    raise KeyError(template_id)


_OPTIONAL_PREFIX = re.compile(r"^\(optional\)\s*", re.IGNORECASE)
_TYPE_PREFIX = re.compile(
    r"^(?:video|reading|lab|project|assignment|quiz)\s*:\s*",
    re.IGNORECASE,
)


def _norm_title(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _title_forms(title: str) -> set[str]:
    """Exact example title, plus the same title with sample type/optional prefixes removed."""
    norm = _norm_title(title)
    if not norm:
        return set()
    forms = {norm}
    rest = _OPTIONAL_PREFIX.sub("", title).strip()
    rest = _TYPE_PREFIX.sub("", rest).strip()
    rest_norm = _norm_title(rest)
    if rest_norm:
        forms.add(rest_norm)
    return forms


def _structural_titles(outline: dict[str, Any]) -> set[str]:
    """Course, module, and task titles. Certificate title is the specialization root check."""
    titles: set[str] = set()

    def add(title: Any) -> None:
        titles.update(_title_forms(str(title or "")))

    def walk_module(module: Any) -> None:
        if not isinstance(module, dict):
            return
        add(module.get("title"))
        for task in module.get("tasks") or []:
            if isinstance(task, dict):
                add(task.get("title"))

    def walk_course(course: Any) -> None:
        if not isinstance(course, dict):
            return
        add(course.get("title"))
        for module in course.get("modules") or []:
            walk_module(module)

    course = outline.get("course")
    if isinstance(course, dict):
        walk_course(course)
    for course in outline.get("courses") or []:
        walk_course(course)
    module = outline.get("module")
    if isinstance(module, dict):
        walk_module(module)
    return titles


@lru_cache(maxsize=1)
def _example_structural_titles() -> frozenset[str]:
    """Placeholder course, module, and task titles from the packaged blank example."""
    return frozenset(_structural_titles(_load_json("blank_hierarchy_v1.json")))


def _root_title_is_placeholder(outline: dict[str, Any], template_id: str) -> bool:
    if template_id == "coursera_specialization":
        cert = outline.get("certificate") or {}
        title = str(cert.get("title") or "").strip()
        return title.startswith("Your program") or title == ""
    if template_id == "coursera_course":
        course = outline.get("course") or {}
        if not course and outline.get("courses"):
            course = (outline["courses"] or [{}])[0]
        title = str(course.get("title") or "").strip()
        return title.startswith("First course") or title == "Course title" or title == ""
    if template_id == "coursera_module":
        module = outline.get("module") or {}
        title = str(module.get("title") or "").strip()
        return title.startswith("Week 1") or title == "Module title" or title == ""
    return False


def is_blank_scaffold(outline: dict[str, Any], template_id: str) -> bool:
    """True when the payload is still the fillable example, even if the root title changed.

    A renamed course or certificate stays a scaffold while example module or task
    titles remain. Replacing those titles is what makes an outline an imported syllabus.
    """
    if template_id not in ("coursera_specialization", "coursera_course", "coursera_module"):
        return False
    if _root_title_is_placeholder(outline, template_id):
        return True
    return bool(_structural_titles(outline) & _example_structural_titles())
