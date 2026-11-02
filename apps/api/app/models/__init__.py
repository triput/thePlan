"""SQLAlchemy ORM models — domain modules with barrel re-exports."""

from app.models.availability import AvailabilityPolicy, AvailabilityWindow
from app.models.calendar import (
    CalendarAccount,
    CalendarSubscription,
    CalendarSubscriptionRefreshFailure,
    ExternalCalendarEvent,
)
from app.models.free_busy_policy import (
    FreeBusyOccurrenceBaseline,
    FreeBusySeriesPolicy,
    FreeBusySeriesPolicyDecision,
)
from app.models.enums import (
    AvailabilityPolicySlug,
    CalendarProvider,
    CalendarSubscriptionRole,
    ReminderChannel,
    ScheduleStatus,
    ScheduleStyle,
    SchedulingAssignmentFamily,
    SchedulingDayPayloadKind,
    SchedulingDayScopedOpKind,
    SchedulingDaySelectorKind,
    SchedulingExceptionOp,
    SchedulingMayPresence,
    SchedulingRuleKind,
    SchedulingScopeKind,
    TaskPriority,
    TimeMapBandTier,
)
from app.models.scheduling_assignment import (
    SchedulingAssignment,
    SchedulingAssignmentRevert,
    SchedulingAssignmentRule,
    SchedulingRuleException,
)
from app.models.scheduling_day_scoped import SchedulingDayScopedOp
from app.models.handoff import HandoffReceipt
from app.models.hierarchy import Epic, FocusWindow, Plan, Project, Section, TimeMapBand
from app.models.label import Label, TaskLabel
from app.models.mixins import TimestampMixin
from app.models.schedule import SchedulePreview, ScheduleRun, ScheduleTaskOutcome
from app.models.task import (
    RecurrenceRule,
    Reminder,
    ScheduledBlock,
    Task,
    TaskDependency,
    TaskProgressEntry,
)
from app.models.task_occurrence_disposition import (
    DispositionCorrectionAudit,
    DispositionEvent,
    ProgressEpochMembership,
    TaskOccurrenceDisposition,
)
from app.models.time_map_override import TimeMapOverride, TimeMapOverrideBand
from app.models.user import AgentCredential, SavedFilter, User, UserSettings

__all__ = [
    "AgentCredential",
    "CalendarAccount",
    "CalendarProvider",
    "CalendarSubscription",
    "CalendarSubscriptionRefreshFailure",
    "AvailabilityPolicy",
    "AvailabilityPolicySlug",
    "AvailabilityWindow",
    "CalendarSubscriptionRole",
    "Epic",
    "ExternalCalendarEvent",
    "FreeBusyOccurrenceBaseline",
    "FreeBusySeriesPolicy",
    "FreeBusySeriesPolicyDecision",
    "FocusWindow",
    "HandoffReceipt",
    "Label",
    "Plan",
    "Project",
    "RecurrenceRule",
    "Reminder",
    "ReminderChannel",
    "SavedFilter",
    "SchedulePreview",
    "ScheduleRun",
    "ScheduleTaskOutcome",
    "ScheduleStatus",
    "ScheduleStyle",
    "ScheduledBlock",
    "SchedulingAssignment",
    "SchedulingAssignmentFamily",
    "SchedulingAssignmentRevert",
    "SchedulingAssignmentRule",
    "SchedulingDayPayloadKind",
    "SchedulingDayScopedOp",
    "SchedulingDayScopedOpKind",
    "SchedulingDaySelectorKind",
    "SchedulingExceptionOp",
    "SchedulingMayPresence",
    "SchedulingRuleException",
    "SchedulingRuleKind",
    "SchedulingScopeKind",
    "Section",
    "Task",
    "TaskDependency",
    "TaskOccurrenceDisposition",
    "DispositionEvent",
    "DispositionCorrectionAudit",
    "ProgressEpochMembership",
    "TaskLabel",
    "TaskProgressEntry",
    "TaskPriority",
    "TimeMapBand",
    "TimeMapBandTier",
    "TimeMapOverride",
    "TimeMapOverrideBand",
    "TimestampMixin",
    "User",
    "UserSettings",
]
