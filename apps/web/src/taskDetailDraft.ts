import type { ScheduleStyle, Task, TaskPriority, TaskUpdate } from "./api";

export const TASK_TITLE_MAX_LENGTH = 500;

export interface TaskDetailDraft {
  title: string;
  description: string;
  priority: TaskPriority;
  dueAtLocal: string;
  softTargetAtLocal: string;
  deadlineAtLocal: string;
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

/** When true, form state should be re-initialized from the server task (not on cache rollback). */
export function shouldResetTaskDetailDraft(
  syncedTaskId: string | null,
  task: Task | null | undefined,
): boolean {
  if (!task) return syncedTaskId !== null;
  return syncedTaskId !== task.id;
}

export function validateTaskDraftForSave(draft: TaskDetailDraft): string | null {
  const trimmed = draft.title.trim();
  if (!trimmed) return "Title is required";
  if (trimmed.length > TASK_TITLE_MAX_LENGTH) {
    return `Title must be ${TASK_TITLE_MAX_LENGTH} characters or fewer`;
  }
  return null;
}

export function buildTaskUpdateFromDraft(_task: Task, draft: TaskDetailDraft): TaskUpdate | null {
  if (validateTaskDraftForSave(draft)) return null;
  const trimmed = draft.title.trim();
  const parsedDuration = draft.duration.trim() ? parseInt(draft.duration, 10) : 0;
  return {
    title: trimmed,
    description: draft.description.trim() || null,
    priority: draft.priority,
    due_at: fromDatetimeLocal(draft.dueAtLocal),
    soft_target_at: fromDatetimeLocal(draft.softTargetAtLocal),
    deadline_at: fromDatetimeLocal(draft.deadlineAtLocal),
    estimated_duration_minutes: Number.isFinite(parsedDuration) ? parsedDuration : 0,
    project_id: draft.projectId || null,
    section_id: draft.projectId && draft.sectionId ? draft.sectionId : null,
    parent_task_id: draft.parentTaskId || null,
    label_ids: draft.labelIds,
    preferred_time_window_id: draft.preferredTimeWindowId || null,
    schedule_style: draft.scheduleStyle || null,
    plan_id: draft.planId || null,
  };
}

function toDatetimeLocal(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
}
