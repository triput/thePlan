import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteTask,
  fetchProjects,
  fetchSections,
  fetchTasks,
  updateTask,
  type Project,
  type Task,
  type TaskPriority,
  type TaskUpdate,
} from "../api";
import { ConfirmDialog } from "./ConfirmDialog";

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

export function TaskDetailPanel({ task, allTasks, onClose }: TaskDetailPanelProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("p4");
  const [dueAtLocal, setDueAtLocal] = useState("");
  const [duration, setDuration] = useState("");
  const [projectId, setProjectId] = useState<string>("");
  const [sectionId, setSectionId] = useState<string>("");
  const [parentTaskId, setParentTaskId] = useState<string>("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: () => fetchProjects() });
  const projects: Project[] = projectsQuery.data?.items ?? [];

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
        ? fetchTasks({ project_id: effectiveProjectId, limit: 200 })
        : fetchTasks({ inbox: true, limit: 200 }),
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
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteTask(task!.id),
    onSuccess: () => {
      invalidate();
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
        onConfirm={() => deleteMutation.mutate()}
      />
    </>
  );
}
