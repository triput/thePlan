from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Epic, FocusWindow, Plan, Project, Section, Task, User


def verify_owned_epic(db: Session, epic_id: uuid.UUID, user: User) -> Epic:
    epic = db.get(Epic, epic_id)
    if epic is None or epic.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epic not found")
    return epic


def verify_owned_project(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def verify_owned_section(db: Session, section_id: uuid.UUID, user: User) -> Section:
    section = db.get(Section, section_id)
    if section is None or section.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


def verify_owned_task(db: Session, task_id: uuid.UUID, user: User) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def verify_owned_focus_window(db: Session, window_id: uuid.UUID, user: User) -> FocusWindow:
    window = db.get(FocusWindow, window_id)
    if window is None or window.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Focus window not found")
    return window


def verify_owned_plan(db: Session, plan_id: uuid.UUID, user: User) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None or plan.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan
