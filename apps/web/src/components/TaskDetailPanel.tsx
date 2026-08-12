import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTaskReminder,
  deleteReminder,
  deleteTask,
  deleteTaskRecurrence,
  fetchFocusWindows,
  fetchLabels,
  fetchPlans,
  fetchProjects,
  fetchSections,
  fetchTaskReminders,
  fetchTasks,
  putTaskRecurrence,
  updateTask,
  type FocusWindow,
  type Label,
  type Plan,
  type Project,
  type ReminderChannel,
  type Task,
  type TaskPriority,
  type TaskUpdate,
} from "../api";
import { collectDeleteTree, useUndoStack } from "../undoStack";
import { ConfirmDialog } from "./ConfirmDialog";
import { emitToast } from "./ToastHost";

interface TaskDetailPanelProps {
  task: Task | null;
  allTasks: Task[];
  onClose: () => void;
}

const PRIORITIES: TaskPriority[] = ["p1", "p2", "p3", "p4"];

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

function isDescendantOf(candidate: Task, ancestorId: string, byId: Map<string, Task>): boolean {
  let current: Task | undefined = candidate;
  const seen = new Set<string>();
  while (current?.parent_task_id) {
    if (current.parent_task_id === ancestorId) return true;
    if (seen.has(current.parent_task_id)) break;
    seen.add(current.parent_task_id);
    current = byId.get(current.parent_task_id);
  }
  return false;
}

function applyTaskUpdate(task: Task, body: TaskUpdate): Task {
  return {
    ...task,
    title: body.title ?? task.title,
    description: body.description !== undefined ? body.description : task.description,
    project_id: body.project_id !== undefined ? body.project_id : task.project_id,
    section_id: body.section_id !== undefined ? body.section_id : task.section_id,
    parent_task_id:
      body.parent_task_id !== undefined ? body.parent_task_id : task.parent_task_id,
    priority: body.priority ?? task.priority,
    due_at: body.due_at !== undefined ? body.due_at : task.due_at,
    deadline_at: body.deadline_at !== undefined ? body.deadline_at : task.deadline_at,
    soft_target_at:
      body.soft_target_at !== undefined ? body.soft_target_at : task.soft_target_at,
    plan_id: body.plan_id !== undefined ? body.plan_id : task.plan_id,
    estimated_duration_minutes:
      body.estimated_duration_minutes ?? task.estimated_duration_minutes,
    preferred_time_window_id:
      body.preferred_time_window_id !== undefined
        ? body.preferred_time_window_id
        : task.preferred_time_window_id,
    label_ids: body.label_ids ?? task.label_ids,
  };
}

export function TaskDetailPanel({ task, allTasks, onClose }: TaskDetailPanelProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("p4");
  const [dueAtLocal, setDueAtLocal] = useState("");
  const [softTargetAtLocal, setSoftTargetAtLocal] = useState("");
  const [deadlineAtLocal, setDeadlineAtLocal] = useState("");
  const [duration, setDuration] = useState("");
  const [projectId, setProjectId] = useState<string>("");
  const [sectionId, setSectionId] = useState<string>("");
  const [parentTaskId, setParentTaskId] = useState<string>("");
  const [labelIds, setLabelIds] = useState<string[]>([]);
  const [preferredTimeWindowId, setPreferredTimeWindowId] = useState<string>("");
  const [planId, setPlanId] = useState<string>("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [recurrenceText, setRecurrenceText] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [reminderAtLocal, setReminderAtLocal] = useState("");
  const [reminderChannel, setReminderChannel] = useState<ReminderChannel>("in_app");
  const [notifPermission, setNotifPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  const queryClient = useQueryClient();
  const { push } = useUndoStack();

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const projects: Project[] = projectsQuery.data?.items ?? [];

  const labelsQuery = useQuery({ queryKey: ["labels"], queryFn: () => fetchLabels({ limit: 200 }) });
  const allLabels: Label[] = labelsQuery.data?.items ?? [];

  const focusWindowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled: task !== null,
  });
  const focusWindows: FocusWindow[] = focusWindowsQuery.data ?? [];

  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: fetchPlans,
    enabled: task !== null,
  });
  const plans: Plan[] = plansQuery.data ?? [];

  const effectiveProjectId = projectId || null;

  const sectionsQuery = useQuery({
    queryKey: ["sections", effectiveProjectId],
    queryFn: () => fetchSections(effectiveProjectId!),
    enabled: effectiveProjectId !== null,
  });
  const sections = sectionsQuery.data?.items ?? [];

  const parentCandidatesQuery = useQuery({
    queryKey: ["tasks", "parents", effectiveProjectId],
    queryFn: () =>
      effectiveProjectId
        ? fetchTasks({ project_id: effectiveProjectId, limit: 200, is_completed: false })
        : fetchTasks({ inbox: true, limit: 200, is_completed: false }),
    enabled: task !== null,
  });
  const parentCandidates = parentCandidatesQuery.data?.items ?? [];

  useEffect(() => {
    if (!task) return;
    setTitle(task.title);
    setDescription(task.description ?? "");
    setPriority(task.priority);
    setDueAtLocal(toDatetimeLocal(task.due_at));
    setSoftTargetAtLocal(toDatetimeLocal(task.soft_target_at));
    setDeadlineAtLocal(toDatetimeLocal(task.deadline_at));
    setDuration(task.estimated_duration_minutes > 0 ? String(task.estimated_duration_minutes) : "");
    setProjectId(task.project_id ?? "");
    setSectionId(task.section_id ?? "");
    setParentTaskId(task.parent_task_id ?? "");
    setLabelIds(task.label_ids);
    setPreferredTimeWindowId(task.preferred_time_window_id ?? "");
    setPlanId(task.plan_id ?? "");
    setRecurrenceText("");
    setStartsOn(task.recurrence?.starts_on ?? "");
    setEndsOn(task.recurrence?.ends_on ?? "");
    setReminderAtLocal("");
    setReminderChannel("in_app");
  }, [task]);

  const remindersQuery = useQuery({
    queryKey: ["reminders", task?.id],
    queryFn: () => fetchTaskReminders(task!.id),
    enabled: task != null,
  });
  const reminders = remindersQuery.data ?? [];
  const upcomingReminders = reminders.filter((r) => !r.is_fired);

  const byId = useMemo(() => new Map(allTasks.map((t) => [t.id, t])), [allTasks]);

  const parentOptions = useMemo(() => {
    if (!task) return [];
    return parentCandidates.filter(
      (t) =>
        t.id !== task.id &&
        !isDescendantOf(t, task.id, byId) &&
        t.nesting_level < 2,
    );
  }, [parentCandidates, task, byId]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["tasks"] });

  const updateMutation = useMutation({
    mutationFn: (body: TaskUpdate) => updateTask(task!.id, body),
    onMutate: async (body) => {
      const taskKey = ["task", task!.id];
      await queryClient.cancelQueries({ queryKey: taskKey });
      const previousTask = queryClient.getQueryData<Task>(taskKey);
      const previousTasksEntries = queryClient
        .getQueriesData<{ items: Task[]; total: number }>({ queryKey: ["tasks"] })
        .map(([key, data]) => ({ key, data }));

      if (previousTask) {
        queryClient.setQueryData(taskKey, applyTaskUpdate(previousTask, body));
      }

      for (const { key, data } of previousTasksEntries) {
        if (!data) continue;
        queryClient.setQueryData(key, {
          ...data,
          items: data.items.map((t) =>
            t.id === task!.id ? applyTaskUpdate(t, body) : t,
          ),
        });
      }

      return { previousTask, previousTasksEntries, taskKey };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousTask) {
        queryClient.setQueryData(context.taskKey, context.previousTask);
      }
      for (const { key, data } of context?.previousTasksEntries ?? []) {
        queryClient.setQueryData(key, data);
      }
      emitToast("Couldn't save — reverted");
    },
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["task", task!.id] });
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const tree = await collectDeleteTree(task!);
      await deleteTask(task!.id);
      return tree;
    },
    onSuccess: (tree) => {
      push({ type: "delete_tree", nodes: tree });
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["search"] });
      queryClient.invalidateQueries({ queryKey: ["task"] });
      setConfirmDelete(false);
      onClose();
    },
  });

  const recurrenceMutation = useMutation({
    mutationFn: async () => {
      const trimmed = recurrenceText.trim();
      if (!trimmed) {
        await deleteTaskRecurrence(task!.id);
        return;
      }
      await putTaskRecurrence(task!.id, {
        text: trimmed.toLowerCase().startsWith("every") ? trimmed : `every ${trimmed}`,
        starts_on: startsOn || null,
        ends_on: endsOn || null,
      });
    },
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["task", task!.id] });
      emitToast("Recurrence saved");
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't save recurrence"),
  });

  const clearRecurrenceMutation = useMutation({
    mutationFn: () => deleteTaskRecurrence(task!.id),
    onSuccess: () => {
      setRecurrenceText("");
      setStartsOn("");
      setEndsOn("");
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["task", task!.id] });
      emitToast("Recurrence cleared");
    },
  });

  const createReminderMutation = useMutation({
    mutationFn: async () => {
      const fireAt = fromDatetimeLocal(reminderAtLocal);
      if (!fireAt) throw new Error("Pick a reminder time");
      return createTaskReminder(task!.id, { fire_at: fireAt, channel: reminderChannel });
    },
    onSuccess: () => {
      setReminderAtLocal("");
      queryClient.invalidateQueries({ queryKey: ["reminders", task!.id] });
      emitToast("Reminder added");
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't add reminder"),
  });

  const deleteReminderMutation = useMutation({
    mutationFn: (reminderId: string) => deleteReminder(reminderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reminders", task!.id] });
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't delete reminder"),
  });

  const requestBrowserNotifications = async () => {
    if (typeof Notification === "undefined") {
      setNotifPermission("unsupported");
      return;
    }
    const permission = await Notification.requestPermission();
    setNotifPermission(permission);
    if (permission === "granted") emitToast("Browser notifications enabled");
    else if (permission === "denied") emitToast("Browser notifications blocked");
  };

  const handleProjectChange = (value: string) => {
    setProjectId(value);
    setSectionId("");
    if (value) {
      const stillValid = sections.some((s) => s.id === sectionId);
      if (!stillValid) setSectionId("");
    }
  };

  const toggleLabel = (labelId: string) => {
    setLabelIds((prev) =>
      prev.includes(labelId) ? prev.filter((id) => id !== labelId) : [...prev, labelId],
    );
  };

  const handlePlanChange = (value: string) => {
    setPlanId(value);
    if (value) {
      const plan = plans.find((p) => p.id === value);
      if (plan?.soft_target_at) {
        setSoftTargetAtLocal(toDatetimeLocal(plan.soft_target_at));
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task) return;
    const trimmed = title.trim();
    if (!trimmed) return;
    const parsedDuration = duration.trim() ? parseInt(duration, 10) : 0;
    updateMutation.mutate({
      title: trimmed,
      description: description.trim() || null,
      priority,
      due_at: fromDatetimeLocal(dueAtLocal),
      soft_target_at: fromDatetimeLocal(softTargetAtLocal),
      deadline_at: fromDatetimeLocal(deadlineAtLocal),
      estimated_duration_minutes: Number.isFinite(parsedDuration) ? parsedDuration : 0,
      project_id: projectId || null,
      section_id: projectId && sectionId ? sectionId : null,
      parent_task_id: parentTaskId || null,
      label_ids: labelIds,
      preferred_time_window_id: preferredTimeWindowId || null,
      plan_id: planId || null,
    });
  };

  if (!task) return null;

  return (
    <>
      <aside className="task-detail-panel task-detail-sheet" aria-label="Task details">
        <header className="detail-header">
          <h2>Task details</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close panel">
            ×
          </button>
        </header>
        <form className="entity-form detail-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Title</span>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              className="field-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder="Notes, links, context…"
            />
          </label>
          <label className="field">
            <span>Priority</span>
            <select
              className="field-select"
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority)}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Due</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={dueAtLocal}
              onChange={(e) => setDueAtLocal(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Soft target</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={softTargetAtLocal}
              onChange={(e) => setSoftTargetAtLocal(e.target.value)}
            />
            <span className="field-hint muted small">
              Flexible plan target — scheduler may slide
            </span>
          </label>
          <label className="field">
            <span>Deadline</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={deadlineAtLocal}
              onChange={(e) => setDeadlineAtLocal(e.target.value)}
            />
            <span className="field-hint muted small">
              Hard commit — scheduler must not miss
            </span>
          </label>

          <label className="field">
            <span>Plan</span>
            <select
              className="field-select"
              value={planId}
              onChange={(e) => handlePlanChange(e.target.value)}
            >
              <option value="">None</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name}
                </option>
              ))}
            </select>
            <span className="field-hint muted small">
              Assigning a plan may copy its soft target onto this task
            </span>
          </label>

          <fieldset className="field recurrence-fieldset">
            <legend>Recurrence</legend>
            {task.recurrence?.display && (
              <p className="muted small recurrence-current">{task.recurrence.display}</p>
            )}
            <label className="field">
              <span>Pattern</span>
              <input
                type="text"
                value={recurrenceText}
                onChange={(e) => setRecurrenceText(e.target.value)}
                placeholder="every monday, wednesday"
              />
              <span className="field-hint muted small">
                Use every / every! plus day, week, or weekdays. Optional frame below.
              </span>
            </label>
            <div className="recurrence-frame-row">
              <label className="field">
                <span>From</span>
                <input
                  type="date"
                  value={startsOn}
                  onChange={(e) => setStartsOn(e.target.value)}
                />
              </label>
              <label className="field">
                <span>Until</span>
                <input
                  type="date"
                  value={endsOn}
                  onChange={(e) => setEndsOn(e.target.value)}
                />
              </label>
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="btn secondary small"
                disabled={!task.recurrence || clearRecurrenceMutation.isPending}
                onClick={() => clearRecurrenceMutation.mutate()}
              >
                Clear
              </button>
              <button
                type="button"
                className="btn primary small"
                disabled={recurrenceMutation.isPending}
                onClick={() => recurrenceMutation.mutate()}
              >
                {recurrenceMutation.isPending ? "Saving…" : "Save recurrence"}
              </button>
            </div>
          </fieldset>

          <fieldset className="field recurrence-fieldset">
            <legend>Reminders</legend>
            {upcomingReminders.length > 0 ? (
              <ul className="reminder-list">
                {upcomingReminders.map((reminder) => (
                  <li key={reminder.id} className="reminder-row">
                    <span>
                      {new Date(reminder.fire_at).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                      <span className="muted small"> · {reminder.channel === "browser" ? "browser" : "in-app"}</span>
                    </span>
                    <button
                      type="button"
                      className="btn secondary small"
                      disabled={deleteReminderMutation.isPending}
                      onClick={() => deleteReminderMutation.mutate(reminder.id)}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No upcoming reminders</p>
            )}
            <div className="reminder-add-row">
              <label className="field">
                <span>When</span>
                <input
                  type="datetime-local"
                  className="field-datetime"
                  value={reminderAtLocal}
                  onChange={(e) => setReminderAtLocal(e.target.value)}
                />
              </label>
              <label className="field">
                <span>Channel</span>
                <select
                  className="field-select"
                  value={reminderChannel}
                  onChange={(e) => setReminderChannel(e.target.value as ReminderChannel)}
                >
                  <option value="in_app">In-app toast</option>
                  <option value="browser">Browser notification</option>
                </select>
              </label>
            </div>
            {notifPermission !== "unsupported" && notifPermission !== "granted" && (
              <button
                type="button"
                className="btn secondary small reminder-notif-btn"
                onClick={() => void requestBrowserNotifications()}
              >
                Enable browser notifications
              </button>
            )}
            <div className="form-actions">
              <button
                type="button"
                className="btn primary small"
                disabled={!reminderAtLocal || createReminderMutation.isPending}
                onClick={() => createReminderMutation.mutate()}
              >
                {createReminderMutation.isPending ? "Adding…" : "Add reminder"}
              </button>
            </div>
          </fieldset>

          <label className="field">
            <span>Duration (minutes)</span>
            <input
              type="number"
              className="field-number"
              min={0}
              step={5}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="30"
            />
          </label>
          <label className="field">
            <span>Time Map</span>
            <select
              className="field-select"
              value={preferredTimeWindowId}
              onChange={(e) => setPreferredTimeWindowId(e.target.value)}
            >
              <option value="">None</option>
              {focusWindows.map((window) => (
                <option key={window.id} value={window.id}>
                  {window.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Project</span>
            <select
              className="field-select"
              value={projectId}
              onChange={(e) => handleProjectChange(e.target.value)}
            >
              <option value="">Inbox</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
          </label>
          {projectId && (
            <label className="field">
              <span>Section</span>
              <select
                className="field-select"
                value={sectionId}
                onChange={(e) => setSectionId(e.target.value)}
              >
                <option value="">None</option>
                {sections.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="field">
            <span>Parent task</span>
            <select
              className="field-select"
              value={parentTaskId}
              onChange={(e) => setParentTaskId(e.target.value)}
            >
              <option value="">None (top-level)</option>
              {parentOptions.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="field">
            <legend>Labels</legend>
            {allLabels.length === 0 && (
              <p className="muted small">No labels yet. Create labels from the sidebar.</p>
            )}
            <div className="label-toggle-group" role="group" aria-label="Task labels">
              {allLabels.map((label) => {
                const selected = labelIds.includes(label.id);
                return (
                  <button
                    key={label.id}
                    type="button"
                    className={`label-toggle${selected ? " selected" : ""}`}
                    style={
                      selected
                        ? {
                            backgroundColor: `color-mix(in srgb, ${label.color_hex} 22%, transparent)`,
                            borderColor: label.color_hex,
                            color: label.color_hex,
                          }
                        : { borderColor: label.color_hex, color: label.color_hex }
                    }
                    aria-pressed={selected}
                    onClick={() => toggleLabel(label.id)}
                  >
                    <span
                      className="label-swatch tiny"
                      style={{ backgroundColor: label.color_hex }}
                      aria-hidden
                    />
                    {label.name}
                  </button>
                );
              })}
            </div>
          </fieldset>
          {updateMutation.isError && (
            <p className="form-error">{(updateMutation.error as Error).message}</p>
          )}
          <div className="form-actions">
            <button type="button" className="btn secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn primary" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving…" : "Save"}
            </button>
          </div>
          <div className="form-actions destructive-row">
            <button
              type="button"
              className="btn ghost danger-text"
              onClick={() => setConfirmDelete(true)}
            >
              Delete task
            </button>
          </div>
        </form>
      </aside>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete task?"
        message={`Permanently delete "${task.title}"? Subtasks may be affected.`}
        confirmLabel="Delete"
        destructive
        pending={deleteMutation.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => {
          deleteMutation.mutate();
        }}
      />
    </>
  );
}
