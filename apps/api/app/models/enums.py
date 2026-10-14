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


class SchedulingScopeKind(str, enum.Enum):
    """Entity scope for a local scheduling assignment (V4)."""

    task = "task"
    project = "project"
    epic = "epic"


class SchedulingRuleKind(str, enum.Enum):
    may = "may"
    must = "must"
    prefer = "prefer"


class SchedulingMayPresence(str, enum.Enum):
    """Local May representation (V4-P3). omit = inherit; explicit may be empty."""

    omit = "omit"
    explicit = "explicit"


class SchedulingAssignmentFamily(str, enum.Enum):
    none = "none"
    legacy = "legacy"
    new_rule = "new_rule"


class SchedulingExceptionOp(str, enum.Enum):
    replace_named = "replace_named"
    waive_named = "waive_named"


class SchedulingDayScopedOpKind(str, enum.Enum):
    """Persisted day-scoped op kinds (Discovery §2.1 stubs → storage).

    Stub ``day.change_selected`` → ``change_selected``, etc.
    ``revert_scoped`` and ``remove_named_scoped`` are writers that act on
    existing rows; they are not stored op_kind values.
    """

    change_selected = "change_selected"
    only_allow = "only_allow"
    family_replace_scoped = "family_replace_scoped"
    clear_scoped = "clear_scoped"
    add_scoped = "add_scoped"
    replace_named_scoped = "replace_named_scoped"
    waive_named_scoped = "waive_named_scoped"


class SchedulingDaySelectorKind(str, enum.Enum):
    """Civil selector kind. Lifetime / expiry are separate (R1)."""

    one_date = "one_date"
    weekday_standing = "weekday_standing"
    date_range = "date_range"


class SchedulingDayPayloadKind(str, enum.Enum):
    """Distinct omit vs empty vs windows (V4-P3 / §2.1).

    ``none`` — no windows payload (clear / waive).
    ``empty`` — explicit empty set (no ancestor / General fall-through).
    ``policy`` — windows from an owned availability policy.
    ``family`` — scoped family-replace target payload (JSONB).
    """

    none = "none"
    empty = "empty"
    policy = "policy"
    family = "family"
