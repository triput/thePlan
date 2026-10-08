/** HTML5 drag payload: task list/sidebar → calendar drop (W2c). */
export const TASK_CALENDAR_DRAG_MIME = "application/x-theplan-task-calendar-drag";

export type TaskCalendarDragPayload = {
  taskId: string;
  title: string;
  estimatedDurationMinutes: number;
};

export function serializeTaskCalendarDrag(payload: TaskCalendarDragPayload): string {
  return JSON.stringify(payload);
}

export function parseTaskCalendarDrag(raw: string): TaskCalendarDragPayload | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<TaskCalendarDragPayload>;
    if (typeof parsed.taskId !== "string" || !parsed.taskId) return null;
    return {
      taskId: parsed.taskId,
      title: typeof parsed.title === "string" ? parsed.title : "Task",
      estimatedDurationMinutes:
        typeof parsed.estimatedDurationMinutes === "number" &&
        Number.isFinite(parsed.estimatedDurationMinutes)
          ? Math.max(0, Math.floor(parsed.estimatedDurationMinutes))
          : 0,
    };
  } catch {
    return null;
  }
}

export function readTaskCalendarDrag(dataTransfer: DataTransfer): TaskCalendarDragPayload | null {
  const raw = dataTransfer.getData(TASK_CALENDAR_DRAG_MIME);
  return parseTaskCalendarDrag(raw);
}

export function blockDurationMinutesForTask(
  estimatedDurationMinutes: number,
  defaultEstimatedDurationMinutes: number,
): number {
  if (estimatedDurationMinutes > 0) return estimatedDurationMinutes;
  if (defaultEstimatedDurationMinutes > 0) return defaultEstimatedDurationMinutes;
  return 60;
}
