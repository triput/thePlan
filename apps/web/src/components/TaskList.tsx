import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  completeTask,
  createTask,
  fetchLabels,
  fetchSections,
  fetchTasks,
  reorderSections,
  reorderTasks,
  uncompleteTask,
  type Label,
  type Section,
  type Task,
} from "../api";
import { PRIORITY_COLORS } from "../colors";
import { buildReorderSwap, canReorderDown, canReorderUp } from "../reorder";
import {
  formatDue,
  formatDuration,
  isToday,
  isUpcoming,
  viewKey,
  type ViewSelection,
} from "../view";
import { CompleteDialog } from "./CompleteDialog";
import { CreateSectionForm } from "./CreateSectionForm";
import { EditSectionForm } from "./EditSectionForm";
import { ReorderButtons } from "./ReorderButtons";
import { TaskDetailPanel } from "./TaskDetailPanel";

interface TaskListProps {
  view: ViewSelection;
  projectTitle?: string;
}

interface PendingComplete {
  taskId: string;
  taskTitle: string;
  openCount: number;
}

export function TaskList({ view, projectTitle }: TaskListProps) {
  const queryClient = useQueryClient();
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [subtaskParentId, setSubtaskParentId] = useState<string | null>(null);
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [pendingComplete, setPendingComplete] = useState<PendingComplete | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [editingSection, setEditingSection] = useState<Section | null>(null);

  const labelsQuery = useQuery({
    queryKey: ["labels"],
    queryFn: () => fetchLabels({ limit: 200 }),
  });
  const labelsById = useMemo(() => {
    const map = new Map<string, Label>();
    for (const label of labelsQuery.data?.items ?? []) {
      map.set(label.id, label);
    }
    return map;
  }, [labelsQuery.data]);

  const tasksQuery = useQuery({
    queryKey: ["tasks", viewKey(view)],
    queryFn: async () => {
      if (view.type === "inbox") {
        return fetchTasks({ inbox: true, limit: 200, is_completed: false });
      }
      if (view.type === "project") {
        return fetchTasks({ project_id: view.projectId, limit: 200 });
      }
      if (view.type === "label") {
        const result = await fetchTasks({
          label_id: view.labelId,
          limit: 200,
          is_completed: false,
        });
        return {
          ...result,
          items: result.items.filter((t) => t.label_ids.includes(view.labelId)),
        };
      }
      return fetchTasks({ limit: 200, is_completed: false });
    },
  });

  const sectionsQuery = useQuery({
    queryKey: ["sections", view.type === "project" ? view.projectId : null],
    queryFn: () => fetchSections(view.type === "project" ? view.projectId : ""),
    enabled: view.type === "project",
  });

  const tasks = useMemo(() => {
    const items = tasksQuery.data?.items ?? [];
    if (view.type === "today") {
      return items.filter((t) => isToday(t.due_at));
    }
    if (view.type === "upcoming") {
      return items.filter((t) => isUpcoming(t.due_at));
    }
    return items;
  }, [tasksQuery.data, view.type]);

  const selectedTask = selectedTaskId ? (tasks.find((t) => t.id === selectedTaskId) ?? null) : null;

  const invalidateTasks = () => {
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: invalidateTasks,
  });

  const completeMutation = useMutation({
    mutationFn: ({
      taskId,
      body,
    }: {
      taskId: string;
      body?: { bulk_children?: boolean; force_parent_only?: boolean };
    }) => completeTask(taskId, body ?? {}),
    onMutate: async ({ taskId }) => {
      const key = ["tasks", viewKey(view)];
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ items: Task[]; total: number }>(key);
      if (previous) {
        queryClient.setQueryData(key, {
          ...previous,
          items: previous.items.map((t) =>
            t.id === taskId ? { ...t, is_completed: true } : t,
          ),
        });
      }
      return { previous, key };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.key, context.previous);
      }
    },
    onSettled: invalidateTasks,
  });

  const uncompleteMutation = useMutation({
    mutationFn: uncompleteTask,
    onSuccess: invalidateTasks,
  });

  const reorderTasksMutation = useMutation({
    mutationFn: reorderTasks,
    onSuccess: invalidateTasks,
  });

  const reorderSectionsMutation = useMutation({
    mutationFn: reorderSections,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sections"] });
    },
  });

  const sections = useMemo(
    () =>
      [...(sectionsQuery.data?.items ?? [])].sort((a, b) => a.sort_order - b.sort_order),
    [sectionsQuery.data],
  );

  const taskSiblings = useMemo(() => {
    const groups = new Map<string, Task[]>();
    for (const task of tasks) {
      const key = `${task.parent_task_id ?? "root"}:${task.section_id ?? "none"}`;
      const group = groups.get(key) ?? [];
      group.push(task);
      groups.set(key, group);
    }
    for (const group of groups.values()) {
      group.sort((a, b) => a.sort_order - b.sort_order);
    }
    return groups;
  }, [tasks]);

  const getTaskSiblings = (task: Task) =>
    taskSiblings.get(`${task.parent_task_id ?? "root"}:${task.section_id ?? "none"}`) ?? [];

  const handleReorderTask = (task: Task, direction: "up" | "down") => {
    const siblings = getTaskSiblings(task);
    const items = buildReorderSwap(siblings, task.id, direction);
    if (items) reorderTasksMutation.mutate({ items });
  };

  const handleReorderSection = (section: Section, direction: "up" | "down") => {
    const items = buildReorderSwap(sections, section.id, direction);
    if (items) reorderSectionsMutation.mutate({ items });
  };

  const handleToggleComplete = async (task: Task) => {
    if (task.is_completed) {
      uncompleteMutation.mutate(task.id);
      return;
    }
    try {
      await completeMutation.mutateAsync({ taskId: task.id });
    } catch (err) {
      if (err instanceof ApiError && err.code === "OPEN_CHILDREN") {
        setPendingComplete({
          taskId: task.id,
          taskTitle: task.title,
          openCount: err.openCount ?? task.open_subtask_count,
        });
      }
    }
  };

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newTaskTitle.trim();
    if (!trimmed) return;
    createMutation.mutate({
      title: trimmed,
      project_id: view.type === "project" ? view.projectId : null,
    });
    setNewTaskTitle("");
  };

  const handleAddSubtask = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = subtaskTitle.trim();
    if (!trimmed || !subtaskParentId) return;
    const parent = tasks.find((t) => t.id === subtaskParentId);
    createMutation.mutate({
      title: trimmed,
      parent_task_id: subtaskParentId,
      project_id: parent?.project_id ?? (view.type === "project" ? view.projectId : null),
      section_id: parent?.section_id ?? null,
    });
    setSubtaskTitle("");
    setSubtaskParentId(null);
  };

  const handleTaskRowClick = (task: Task, e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest("input, button")) return;
    setSelectedTaskId(task.id);
  };

  const heading =
    view.type === "project"
      ? (projectTitle ?? "Project")
      : view.type === "inbox"
        ? "Inbox"
        : view.type === "today"
          ? "Today"
          : view.type === "label"
            ? (labelsById.get(view.labelId)?.name ?? "Label")
            : "Upcoming";

  return (
    <div className={`task-list-layout${selectedTask ? " with-detail" : ""}`}>
      <div className="task-list-pane">
        <header className="pane-header">
          <h1>{heading}</h1>
          {view.type === "project" && <CreateSectionForm projectId={view.projectId} />}
        </header>

        {sections.length > 0 && (
          <div className="sections-bar">
            {sections.map((s) => (
              <span key={s.id} className="section-tag">
                {s.title}
                <ReorderButtons
                  label={s.title}
                  canMoveUp={canReorderUp(sections, s.id)}
                  canMoveDown={canReorderDown(sections, s.id)}
                  onMoveUp={() => handleReorderSection(s, "up")}
                  onMoveDown={() => handleReorderSection(s, "down")}
                  pending={reorderSectionsMutation.isPending}
                  className="section-reorder-btns"
                />
                <button
                  type="button"
                  className="icon-btn tiny section-edit-btn"
                  title={`Edit ${s.title}`}
                  aria-label={`Edit ${s.title}`}
                  onClick={() => setEditingSection(s)}
                >
                  ✎
                </button>
              </span>
            ))}
          </div>
        )}

        {tasksQuery.isLoading && <p className="muted">Loading tasks…</p>}
        {tasksQuery.isError && (
          <p className="form-error">
            Failed to load tasks: {(tasksQuery.error as Error).message}
          </p>
        )}

        <ul className="task-list" aria-label={`Tasks in ${heading}`}>
          {tasks.length === 0 && !tasksQuery.isLoading && (
            <li className="empty-state">No tasks here yet.</li>
          )}
          {tasks.map((task) => {
            const siblings = getTaskSiblings(task);
            return (
            <li
              key={task.id}
              className={`task-row${task.is_completed ? " completed" : ""}${selectedTaskId === task.id ? " selected" : ""}`}
              style={{ paddingLeft: `${12 + task.nesting_level * 20}px` }}
              onClick={(e) => handleTaskRowClick(task, e)}
            >
              <input
                type="checkbox"
                className="task-check"
                checked={task.is_completed}
                onChange={() => handleToggleComplete(task)}
                aria-label={`Mark "${task.title}" complete`}
              />
              <span className={`task-title${task.is_completed ? " done" : ""}`}>{task.title}</span>
              {task.priority !== "p4" && (
                <span
                  className="priority-badge"
                  style={{ color: PRIORITY_COLORS[task.priority] }}
                >
                  {task.priority.toUpperCase()}
                </span>
              )}
              {task.due_at && <span className="due-badge">{formatDue(task.due_at)}</span>}
              {task.estimated_duration_minutes > 0 && (
                <span className="duration-badge">
                  {formatDuration(task.estimated_duration_minutes)}
                </span>
              )}
              {task.label_ids.map((labelId) => {
                const label = labelsById.get(labelId);
                if (!label) return null;
                return (
                  <span
                    key={labelId}
                    className="label-chip"
                    style={{ borderColor: label.color_hex, color: label.color_hex }}
                  >
                    {label.name}
                  </span>
                );
              })}
              <ReorderButtons
                label={task.title}
                canMoveUp={canReorderUp(siblings, task.id)}
                canMoveDown={canReorderDown(siblings, task.id)}
                onMoveUp={() => handleReorderTask(task, "up")}
                onMoveDown={() => handleReorderTask(task, "down")}
                pending={reorderTasksMutation.isPending}
                className="task-reorder-btns"
              />
              {!task.is_completed && (
                <button
                  type="button"
                  className="icon-btn subtask-btn"
                  title="Add subtask"
                  aria-label={`Add subtask to ${task.title}`}
                  onClick={() => {
                    setSubtaskParentId(task.id);
                    setSubtaskTitle("");
                  }}
                >
                  +
                </button>
              )}
            </li>
            );
          })}
        </ul>

        {subtaskParentId && (
          <form className="inline-form subtask-form" onSubmit={handleAddSubtask}>
            <input
              type="text"
              value={subtaskTitle}
              onChange={(e) => setSubtaskTitle(e.target.value)}
              placeholder="Subtask title"
              autoFocus
            />
            <button type="submit" className="btn primary small" disabled={createMutation.isPending}>
              Add subtask
            </button>
            <button
              type="button"
              className="btn secondary small"
              onClick={() => setSubtaskParentId(null)}
            >
              Cancel
            </button>
          </form>
        )}

        <form className="inline-form add-task-form" onSubmit={handleAddTask}>
          <input
            type="text"
            value={newTaskTitle}
            onChange={(e) => setNewTaskTitle(e.target.value)}
            placeholder="Add a task…"
          />
          <button type="submit" className="btn primary small" disabled={createMutation.isPending}>
            Add
          </button>
        </form>

        <CompleteDialog
          open={pendingComplete !== null}
          taskTitle={pendingComplete?.taskTitle ?? ""}
          openCount={pendingComplete?.openCount ?? 0}
          pending={completeMutation.isPending}
          onClose={() => setPendingComplete(null)}
          onParentOnly={() => {
            if (!pendingComplete) return;
            completeMutation.mutate(
              { taskId: pendingComplete.taskId, body: { force_parent_only: true } },
              { onSuccess: () => setPendingComplete(null) },
            );
          }}
          onBulkChildren={() => {
            if (!pendingComplete) return;
            completeMutation.mutate(
              { taskId: pendingComplete.taskId, body: { bulk_children: true } },
              { onSuccess: () => setPendingComplete(null) },
            );
          }}
        />

        <EditSectionForm section={editingSection} onClose={() => setEditingSection(null)} />
      </div>

      <TaskDetailPanel
        task={selectedTask}
        allTasks={tasks}
        onClose={() => setSelectedTaskId(null)}
      />
    </div>
  );
}
