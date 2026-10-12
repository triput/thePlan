import enum


class TaskPriority(str, enum.Enum):
    p1 = "p1"
    p2 = "p2"
    p3 = "p3"
    p4 = "p4"


class ScheduleStatus(str, enum.Enum):
    unscheduled = "unscheduled"
    scheduled = "scheduled"
    pinned = "pinned"
    completed = "completed"
    cancelled = "cancelled"
    overbooked = "overbooked"


class CalendarProvider(str, enum.Enum):
    google = "google"
    microsoft = "microsoft"


class CalendarSubscriptionRole(str, enum.Enum):
    primary = "primary"
    informational = "informational"


class ReminderChannel(str, enum.Enum):
    in_app = "in_app"
    browser = "browser"


class ScheduleStyle(str, enum.Enum):
    standalone = "standalone"
    time_block = "time_block"
    bundle = "bundle"
    manual = "manual"


class TaskWorkflowState(str, enum.Enum):
    ready = "ready"
    in_progress = "in_progress"
    waiting = "waiting"


class TaskBoardColumn(str, enum.Enum):
    """Kanban column including derived Done."""

    ready = "ready"
    in_progress = "in_progress"
    waiting = "waiting"
    done = "done"


class TimeMapBandTier(str, enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class AvailabilityPolicySlug(str, enum.Enum):
    """Stable availability policy identities. Display names are separate."""

    general = "general"
    work = "work"
    personal = "personal"
