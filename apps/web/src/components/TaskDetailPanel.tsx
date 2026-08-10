import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteTask,
  fetchLabels,
  fetchProjects,
  fetchSections,
  fetchTasks,
  updateTask,
  type Label,
  type Project,
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
    estimated_duration_minutes:
      body.estimated_duration_minutes ?? task.estimated_duration_minutes,
    label_ids: body.label_ids ?? task.label_ids,
  };
}

export function TaskDetailPanel({ task, allTasks, onClose }: TaskDetailPanelProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("p4");
  const [dueAtLocal, setDueAtLocal] = useState("");
  const [duration, setDuration] = useState("");
  const [projectId, setProjectId] = useState<string>("");
  const [sectionId, setSectionId] = useState<string>("");
  const [parentTaskId, setParentTaskId] = useState<string>("");
  const [labelIds, setLabelIds] = useState<string[]>([]);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const queryClient = useQueryClient();
  const { push } = useUndoStack();

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const projects: Project[] = projectsQuery.data?.items ?? [];

  const labelsQuery = useQuery({ queryKey: ["labels"], queryFn: () => fetchLabels({ limit: 200 }) });
  const allLabels: Label[] = labelsQuery.data?.items ?? [];

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
    setDuration(task.estimated_duration_minutes > 0 ? String(task.estimated_duration_minutes) : "");
    setProjectId(task.project_id ?? "");
    setSectionId(task.section_id ?? "");
    setParentTaskId(task.parent_task_id ?? "");
    setLabelIds(task.label_ids);
  }, [task]);

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
      estimated_duration_minutes: Number.isFinite(parsedDuration) ? parsedDuration : 0,
      project_id: projectId || null,
      section_id: projectId && sectionId ? sectionId : null,
      parent_task_id: parentTaskId || null,
      label_ids: labelIds,
    });
  };

  if (!task) return null;

  return (
    <>
      <aside className="task-detail-panel" aria-label="Task details">
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
