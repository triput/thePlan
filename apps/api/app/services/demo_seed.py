from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Epic, Label, Project, ScheduledBlock, Section, Task, TaskLabel, User
from app.models.enums import TaskPriority
from app.services.auth_users import create_household_user, is_setup_required, normalize_username

logger = logging.getLogger(__name__)

NEBULA_USERNAME = "nebula"
NEBULA_EMAIL = "nebula@localhost"
NEBULA_DISPLAY_NAME = "Nebula"

_WORDS = (
    "amber",
    "anchor",
    "aurora",
    "breeze",
    "canyon",
    "cedar",
    "comet",
    "coral",
    "delta",
    "ember",
    "falcon",
    "forest",
    "galaxy",
    "harbor",
    "ivory",
    "jade",
    "lunar",
    "meadow",
    "nebula",
    "ocean",
    "orchid",
    "pebble",
    "quartz",
    "river",
    "silver",
    "summit",
    "timber",
    "velvet",
    "willow",
    "zenith",
)


def _generate_passphrase() -> str:
    picks = [secrets.choice(_WORDS) for _ in range(4)]
    return " ".join(picks)


def _write_nebula_credentials(repo_root: Path, password: str) -> Path:
    backup_dir = repo_root / ".secrets-backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    cred_path = backup_dir / "nebula-credentials.txt"
    cred_path.write_text(
        f"username: {NEBULA_USERNAME}\nemail: {NEBULA_EMAIL}\npassword: {password}\n",
        encoding="utf-8",
    )
    return cred_path


def _seed_nebula_data(db: Session, owner_id) -> None:
    now = datetime.now(tz=UTC)
    today = now.replace(hour=9, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=5)

    epic = Epic(
        owner_id=owner_id,
        title="Nebula — Life & Work",
        description="Demo epic for the Nebula household account.",
        color_hex="#6D3FC9",
    )
    db.add(epic)
    db.flush()

    project_a = Project(
        owner_id=owner_id,
        epic_id=epic.id,
        title="Nebula — Home Projects",
        color_hex="#0A8558",
    )
    project_b = Project(
        owner_id=owner_id,
        epic_id=epic.id,
        title="Nebula — Learning",
        color_hex="#2563EB",
    )
    db.add_all([project_a, project_b])
    db.flush()

    section_a = Section(owner_id=owner_id, project_id=project_a.id, title="Nebula — This week")
    section_b = Section(owner_id=owner_id, project_id=project_b.id, title="Nebula — Reading")
    db.add_all([section_a, section_b])
    db.flush()

    labels = [
        Label(owner_id=owner_id, name="nebula-demo", color_hex="#635F75"),
        Label(owner_id=owner_id, name="nebula-urgent", color_hex="#E5484D"),
        Label(owner_id=owner_id, name="nebula-someday", color_hex="#8B5CF6"),
    ]
    db.add_all(labels)
    db.flush()

    tasks: list[Task] = [
        Task(
            owner_id=owner_id,
            title="Nebula — Inbox triage",
            priority=TaskPriority.p2,
            due_at=today,
        ),
        Task(
            owner_id=owner_id,
            title="Nebula — Plan weekly meals",
            priority=TaskPriority.p3,
            due_at=tomorrow,
        ),
        Task(
            owner_id=owner_id,
            project_id=project_a.id,
            section_id=section_a.id,
            title="Nebula — Fix pantry shelves",
            priority=TaskPriority.p2,
            due_at=today + timedelta(hours=3),
        ),
        Task(
            owner_id=owner_id,
            project_id=project_a.id,
            section_id=section_a.id,
            title="Nebula — Replace air filter",
            priority=TaskPriority.p4,
            due_at=next_week,
        ),
        Task(
            owner_id=owner_id,
            project_id=project_b.id,
            section_id=section_b.id,
            title="Nebula — Read chapter 3",
            priority=TaskPriority.p3,
            due_at=tomorrow,
        ),
        Task(
            owner_id=owner_id,
            project_id=project_b.id,
            section_id=section_b.id,
            title="Nebula — Practice typing drills",
            priority=TaskPriority.p4,
            due_at=next_week,
        ),
        Task(
            owner_id=owner_id,
            project_id=project_b.id,
            title="Nebula — Summarize notes",
            priority=TaskPriority.p3,
            is_completed=True,
            completed_at=now - timedelta(days=1),
        ),
        Task(
            owner_id=owner_id,
            title="Nebula — Call dentist",
            priority=TaskPriority.p1,
            due_at=today + timedelta(hours=1),
        ),
        Task(
            owner_id=owner_id,
            project_id=project_a.id,
            title="Nebula — Declutter garage",
            priority=TaskPriority.p4,
            due_at=next_week + timedelta(days=2),
        ),
        Task(
            owner_id=owner_id,
            title="Nebula — Water plants",
            priority=TaskPriority.p3,
            is_completed=True,
            completed_at=now - timedelta(hours=5),
        ),
    ]
    db.add_all(tasks)
    db.flush()

    db.add_all(
        [
            TaskLabel(task_id=tasks[0].id, label_id=labels[1].id),
            TaskLabel(task_id=tasks[2].id, label_id=labels[0].id),
            TaskLabel(task_id=tasks[4].id, label_id=labels[0].id),
            TaskLabel(task_id=tasks[8].id, label_id=labels[2].id),
        ]
    )

    focus_task = tasks[7]
    db.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=focus_task.id,
            start_time=today + timedelta(hours=2),
            end_time=today + timedelta(hours=2, minutes=45),
            is_pinned=False,
        )
    )
    db.add(
        ScheduledBlock(
            owner_id=owner_id,
            task_id=tasks[2].id,
            start_time=tomorrow + timedelta(hours=10),
            end_time=tomorrow + timedelta(hours=11, minutes=30),
            is_pinned=True,
        )
    )


def ensure_demo_nebula(
    db: Session,
    *,
    repo_root: Path,
    configured_password: str | None,
) -> User | None:
    """Create demo user Nebula with fixture data when setup is complete."""
    if is_setup_required(db):
        return None

    norm = normalize_username(NEBULA_USERNAME)
    existing = db.query(User).filter(User.username == norm).one_or_none()
    if existing is not None:
        return existing

    password = configured_password or _generate_passphrase()
    user = create_household_user(
        db,
        username=NEBULA_USERNAME,
        email=NEBULA_EMAIL,
        password=password,
        display_name=NEBULA_DISPLAY_NAME,
        is_admin=False,
    )
    _seed_nebula_data(db, user.id)
    db.commit()
    db.refresh(user)

    if configured_password is None:
        cred_path = _write_nebula_credentials(repo_root, password)
        logger.warning("Nebula demo credentials written to %s", cred_path)

    return user
