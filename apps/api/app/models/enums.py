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


class TimeMapBandTier(str, enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"
