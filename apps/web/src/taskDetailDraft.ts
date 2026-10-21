import type { ScheduleStyle, Task, TaskPriority, TaskUpdate } from "./api";

export const TASK_TITLE_MAX_LENGTH = 500;

export interface TaskDetailDraft {
  title: string;
  description: string;
  priority: TaskPriority;
  dueAtLocal: string;
  softTargetAtLocal: string;
  deadlineAtLocal: string;
  startNoEarlierAtLocal: string;
  startNoLaterAtLocal: string;
  duration: string;
  projectId: string;
  sectionId: string;
  parentTaskId: string;
  labelIds: string[];
  preferredTimeWindowId: string;
  scheduleStyle: "" | ScheduleStyle;
  planId: string;
}

export function taskToDraft(task: Task): TaskDetailDraft {
  return {
    title: task.title,
    description: task.description ?? "",
    priority: task.priority,
    dueAtLocal: toDatetimeLocal(task.due_at),
    softTargetAtLocal: toDatetimeLocal(task.soft_target_at),
    deadlineAtLocal: toDatetimeLocal(task.deadline_at),
    startNoEarlierAtLocal: toDatetimeLocal(task.start_no_earlier_at ?? null),
    startNoLaterAtLocal: toDatetimeLocal(task.start_no_later_at ?? null),
    duration:
      task.estimated_duration_minutes > 0 ? String(task.estimated_duration_minutes) : "",
    projectId: task.project_id ?? "",
    sectionId: task.section_id ?? "",
    parentTaskId: task.parent_task_id ?? "",
    labelIds: task.label_ids,
    preferredTimeWindowId: task.preferred_time_window_id ?? "",
    scheduleStyle: task.schedule_style ?? "",
    planId: task.plan_id ?? "",
  };
}

export function isTaskDraftDirty(task: Task, draft: TaskDetailDraft): boolean {
  const baseline = taskToDraft(task);
  if (draft.title.trim() !== baseline.title.trim()) return true;
  if (draft.description.trim() !== baseline.description.trim()) return true;
  if (draft.priority !== baseline.priority) return true;
  if (draft.dueAtLocal !== baseline.dueAtLocal) return true;
  if (draft.softTargetAtLocal !== baseline.softTargetAtLocal) return true;
  if (draft.deadlineAtLocal !== baseline.deadlineAtLocal) return true;
  if (draft.startNoEarlierAtLocal !== baseline.startNoEarlierAtLocal) return true;
  if (draft.startNoLaterAtLocal !== baseline.startNoLaterAtLocal) return true;
  if (draft.duration.trim() !== baseline.duration.trim()) return true;
  if (draft.projectId !== baseline.projectId) return true;
  if (draft.sectionId !== baseline.sectionId) return true;
  if (draft.parentTaskId !== baseline.parentTaskId) return true;
  if (draft.scheduleStyle !== baseline.scheduleStyle) return true;
  if (draft.preferredTimeWindowId !== baseline.preferredTimeWindowId) return true;
  if (draft.planId !== baseline.planId) return true;
  if (draft.labelIds.length !== baseline.labelIds.length) return true;
  const sortedDraft = [...draft.labelIds].sort();
  const sortedBase = [...baseline.labelIds].sort();
  for (let i = 0; i < sortedDraft.length; i += 1) {
    if (sortedDraft[i] !== sortedBase[i]) return true;
  }
  return false;
}

/** Dirty check for held release date fields only (deadline + occurrence bounds). */
export function isOccurrenceDatesDirty(task: Task, draft: TaskDetailDraft): boolean {
  const baseline = taskToDraft(task);
  return (
    draft.deadlineAtLocal !== baseline.deadlineAtLocal ||
    draft.startNoEarlierAtLocal !== baseline.startNoEarlierAtLocal ||
    draft.startNoLaterAtLocal !== baseline.startNoLaterAtLocal
  );
}

/** When true, form state should be re-initialized from the server task (not on cache rollback). */
export function shouldResetTaskDetailDraft(
  syncedTaskId: string | null,
  task: Task | null | undefined,
): boolean {
  if (!task) return syncedTaskId !== null;
  return syncedTaskId !== task.id;
}

const DATETIME_FIELD_LABELS: ReadonlyArray<readonly [keyof TaskDetailDraft, string]> = [
  ["dueAtLocal", "Due date"],
  ["softTargetAtLocal", "Soft target"],
  ["deadlineAtLocal", "Deadline"],
  ["startNoEarlierAtLocal", "Start no earlier"],
  ["startNoLaterAtLocal", "Start no later"],
];

/** Reject non-empty datetime-local values that do not parse (no silent null). */
export function validateDatetimeLocalFields(draft: TaskDetailDraft): string | null {
  for (const [key, label] of DATETIME_FIELD_LABELS) {
    const value = draft[key];
    if (typeof value !== "string" || !value) continue;
    if (Number.isNaN(new Date(value).getTime())) {
      return `${label} is invalid`;
    }
  }
  return null;
}

export function validateTaskDraftForSave(draft: TaskDetailDraft): string | null {
  const trimmed = draft.title.trim();
  if (!trimmed) return "Title is required";
  if (trimmed.length > TASK_TITLE_MAX_LENGTH) {
    return `Title must be ${TASK_TITLE_MAX_LENGTH} characters or fewer`;
  }
  return validateDatetimeLocalFields(draft);
}

/** Dates-only release: validate deadline + bounds only (title/priority untouched). */
export function validateOccurrenceDatesForSave(draft: TaskDetailDraft): string | null {
  for (const [key, label] of [
    ["deadlineAtLocal", "Deadline"],
    ["startNoEarlierAtLocal", "Start no earlier"],
    ["startNoLaterAtLocal", "Start no later"],
  ] as const) {
    const value = draft[key];
    if (!value) continue;
    if (Number.isNaN(new Date(value).getTime())) {
      return `${label} is invalid`;
    }
  }
  return null;
}

/**
 * Build PATCH body. Deadline + occurrence bounds use omit-unchanged / null-clear
 * (datetime-local is minute-precision — do not re-send unchanged values and truncate seconds).
 * Other date fields keep existing always-send semantics.
 */
export function buildTaskUpdateFromDraft(task: Task, draft: TaskDetailDraft): TaskUpdate | null {
  if (validateTaskDraftForSave(draft)) return null;
  const trimmed = draft.title.trim();
  const parsedDuration = draft.duration.trim() ? parseInt(draft.duration, 10) : 0;
  const baseline = taskToDraft(task);
  const body: TaskUpdate = {
    title: trimmed,
    description: draft.description.trim() || null,
    priority: draft.priority,
    due_at: fromDatetimeLocal(draft.dueAtLocal),
    soft_target_at: fromDatetimeLocal(draft.softTargetAtLocal),
    estimated_duration_minutes: Number.isFinite(parsedDuration) ? parsedDuration : 0,
    project_id: draft.projectId || null,
    section_id: draft.projectId && draft.sectionId ? draft.sectionId : null,
    parent_task_id: draft.parentTaskId || null,
    label_ids: draft.labelIds,
    preferred_time_window_id: draft.preferredTimeWindowId || null,
    schedule_style: draft.scheduleStyle || null,
    plan_id: draft.planId || null,
  };
  if (draft.deadlineAtLocal !== baseline.deadlineAtLocal) {
    body.deadline_at = fromDatetimeLocal(draft.deadlineAtLocal);
  }
  if (draft.startNoEarlierAtLocal !== baseline.startNoEarlierAtLocal) {
    body.start_no_earlier_at = fromDatetimeLocal(draft.startNoEarlierAtLocal);
  }
  if (draft.startNoLaterAtLocal !== baseline.startNoLaterAtLocal) {
    body.start_no_later_at = fromDatetimeLocal(draft.startNoLaterAtLocal);
  }
  return body;
}

/**
 * PATCH body for held "Save dates & release" — deadline + occurrence bounds only.
 * Returns null when validation fails; empty object when nothing date-related changed.
 */
export function buildDatesOnlyUpdateFromDraft(
  task: Task,
  draft: TaskDetailDraft,
): TaskUpdate | null {
  if (validateOccurrenceDatesForSave(draft)) return null;
  const baseline = taskToDraft(task);
  const body: TaskUpdate = {};
  if (draft.deadlineAtLocal !== baseline.deadlineAtLocal) {
    body.deadline_at = fromDatetimeLocal(draft.deadlineAtLocal);
  }
  if (draft.startNoEarlierAtLocal !== baseline.startNoEarlierAtLocal) {
    body.start_no_earlier_at = fromDatetimeLocal(draft.startNoEarlierAtLocal);
  }
  if (draft.startNoLaterAtLocal !== baseline.startNoLaterAtLocal) {
    body.start_no_later_at = fromDatetimeLocal(draft.startNoLaterAtLocal);
  }
  return body;
}

export function toDatetimeLocal(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  // datetime-local is minute precision (browser local zone — not settings timezone).
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

/** IANA zone from the browser (datetime-local convention). Never invents "UTC". */
export function browserTimeZoneLabel(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "browser local";
  } catch {
    return "browser local";
  }
}

/** Format an ISO instant for display with an explicit zone label (settings timezone). */
export function formatInstantInZone(iso: string | null | undefined, timeZone: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  try {
    const formatted = new Intl.DateTimeFormat(undefined, {
      timeZone,
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(d);
    return formatted;
  } catch {
    return d.toISOString();
  }
}
