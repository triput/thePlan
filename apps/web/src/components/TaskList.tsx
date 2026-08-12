import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  completeTask,
  createTask,
  fetchLabels,
  fetchPlans,
  fetchScheduledBlocks,
  fetchSections,
  fetchTasks,
  reorderSections,
  reorderTasks,
  uncompleteTask,
  type Label,
  type Section,
  type Task,
} from "../api";
import { fetchOpenDescendantIds, useUndoStack } from "../undoStack";
import { PRIORITY_COLORS } from "../colors";
import { buildReorderSwap, canReorderDown, canReorderUp } from "../reorder";
import {
  endOfLocalDay,
  formatDue,
  formatDuration,
  isToday,
  isUpcoming,
  rangeOverlapsLocalDay,
  startOfLocalDay,
  viewKey,
  type ViewSelection,
} from "../view";
import { CompleteDialog } from "./CompleteDialog";
import { CreateSectionForm } from "./CreateSectionForm";
import { EditSectionForm } from "./EditSectionForm";
import { emitToast } from "./ToastHost";
import { ReorderButtons } from "./ReorderButtons";

interface TaskListProps {
  view: ViewSelection;
  projectTitle?: string;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string | null) => void;
}

interface PendingComplete {
  taskId: string;
  taskTitle: string;
  openCount: number;
}

const SHOW_COMPLETED_KEY = "theplan.showCompleted";

function readShowCompleted(): boolean {
  try {
    return localStorage.getItem(SHOW_COMPLETED_KEY) === "1";
  } catch {
    return false;
  }
}

function writeShowCompleted(value: boolean) {
  try {
    localStorage.setItem(SHOW_COMPLETED_KEY, value ? "1" : "0");
  } catch {
    /* ignore quota / private mode */
  }
}

function tasksCacheKey(view: ViewSelection, showCompleted: boolean) {
  return ["tasks", viewKey(view), showCompleted ? "with-completed" : "active"] as const;
}

function makeOptimisticTask(body: {
  title: string;
  project_id?: string | null;
  section_id?: string | null;
  parent_task_id?: string | null;
  nesting_level: number;
}): Task {
  return {
    id: `temp-${crypto.randomUUID()}`,
    title: body.title,
    description: null,
    project_id: body.project_id ?? null,
    section_id: body.section_id ?? null,
    parent_task_id: body.parent_task_id ?? null,
    nesting_level: body.nesting_level,
    priority: "p4",
    due_at: null,
    deadline_at: null,
    soft_target_at: null,
    plan_id: null,
    plan_name: null,
    schedule_style: null,
    estimated_duration_minutes: 0,
    preferred_time_window_id: null,
    is_completed: false,
    completed_at: null,
    status: "open",
    sort_order: 9999,
    label_ids: [],
    open_subtask_count: 0,
  };
}

export function TaskList({
  view,
  projectTitle,
  selectedTaskId,
  onSelectTask,
}: TaskListProps) {
  const queryClient = useQueryClient();
  const { push } = useUndoStack();
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [subtaskParentId, setSubtaskParentId] = useState<string | null>(null);
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [pendingComplete, setPendingComplete] = useState<PendingComplete | null>(null);
  const [editingSection, setEditingSection] = useState<Section | null>(null);
  const [focusedTaskId, setFocusedTaskId] = useState<string | null>(null);
  const [showCompleted, setShowCompleted] = useState(readShowCompleted);
  const rowRefs = useRef<Map<string, HTMLLIElement>>(new Map());

  const setShowCompletedPersisted = useCallback((next: boolean) => {
    setShowCompleted(next);
    writeShowCompleted(next);
  }, []);

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

  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: fetchPlans,
  });
  const planNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const plan of plansQuery.data ?? []) {
      map.set(plan.id, plan.name);
    }
    return map;
  }, [plansQuery.data]);

  const tasksQuery = useQuery({
    queryKey: tasksCacheKey(view, showCompleted),
    queryFn: async () => {
      const base =
        view.type === "inbox"
          ? { inbox: true as const, limit: 200 }
          : view.type === "project"
            ? { project_id: view.projectId, limit: 200 }
            : view.type === "epic"
              ? { epic_id: view.epicId, limit: 200 }
              : view.type === "label"
                ? { label_id: view.labelId, limit: 200 }
                : { limit: 200 };

      const load = async (is_completed?: boolean) => {
        const result = await fetchTasks(
          is_completed === undefined ? base : { ...base, is_completed },
        );
        if (view.type === "label") {
          return {
            ...result,
            items: result.items.filter((t) => t.label_ids.includes(view.labelId)),
          };
        }
        return result;
      };

      if (!showCompleted) {
        return load(false);
      }

      // Two requests so open tasks are not crowded out of the 200 limit by history.
      const [open, done] = await Promise.all([load(false), load(true)]);
      const byId = new Map<string, Task>();
      for (const task of [...open.items, ...done.items]) {
        byId.set(task.id, task);
      }
      const items = [...byId.values()].sort((a, b) => {
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.id.localeCompare(b.id);
      });
      return {
        items,
        total: open.total + done.total,
        limit: 200,
        offset: 0,
      };
    },
  });

  const smartRange = useMemo(() => {
    if (view.type === "today") {
      return { start: startOfLocalDay(new Date()), end: endOfLocalDay(new Date()) };
    }
    if (view.type === "upcoming") {
      const start = endOfLocalDay(new Date());
      const end = startOfLocalDay(new Date());
      end.setDate(end.getDate() + 8);
      return { start, end };
    }
    return null;
  }, [view.type]);

  const blocksQuery = useQuery({
    queryKey: ["scheduled-blocks", viewKey(view), smartRange?.start.toISOString()],
    queryFn: () =>
      fetchScheduledBlocks({
        start: smartRange!.start.toISOString(),
        end: smartRange!.end.toISOString(),
      }),
    enabled: smartRange !== null,
  });

  const sectionsQuery = useQuery({
    queryKey: ["sections", view.type === "project" ? view.projectId : null],
    queryFn: () => fetchSections(view.type === "project" ? view.projectId : ""),
    enabled: view.type === "project",
  });

  const tasks = useMemo(() => {
    let items = tasksQuery.data?.items ?? [];
    if (!showCompleted) {
      items = items.filter((t) => !t.is_completed);
    }
    if (view.type === "today") {
      const scheduledIds = new Set(
        (blocksQuery.data?.items ?? [])
          .filter((b) => rangeOverlapsLocalDay(b.start_time, b.end_time, new Date()))
          .map((b) => b.task_id),
      );
      return items.filter((t) => isToday(t.due_at) || scheduledIds.has(t.id));
    }
    if (view.type === "upcoming") {
      const scheduledIds = new Set((blocksQuery.data?.items ?? []).map((b) => b.task_id));
      return items.filter((t) => isUpcoming(t.due_at) || scheduledIds.has(t.id));
    }
    return items;
  }, [tasksQuery.data, blocksQuery.data, view.type, showCompleted]);

  const invalidateTasks = () => {
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const createMutation = useMutation({
    mutationFn: createTask,
    onMutate: async (body) => {
      const key = [...tasksCacheKey(view, showCompleted)];
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ items: Task[]; total: number }>(key);
      const cachedItems = previous?.items ?? [];
      const parent = body.parent_task_id
        ? cachedItems.find((t) => t.id === body.parent_task_id)
        : undefined;
      const tempTask = makeOptimisticTask({
        title: body.title,
        project_id: body.project_id,
        section_id: body.section_id,
        parent_task_id: body.parent_task_id,
        nesting_level: parent ? parent.nesting_level + 1 : 0,
      });
      if (previous) {
        queryClient.setQueryData(key, {
          ...previous,
          items: [...previous.items, tempTask],
          total: previous.total + 1,
        });
      }
      return { previous, key, tempId: tempTask.id };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.key, context.previous);
      }
      emitToast("Couldn't create task — reverted");
    },
    onSuccess: invalidateTasks,
    onSettled: invalidateTasks,
  });

  const completeMutation = useMutation({
    mutationFn: ({
      taskId,
      body,
    }: {
      taskId: string;
      body?: { bulk_children?: boolean; force_parent_only?: boolean };
      undoTaskIds?: string[];
    }) => completeTask(taskId, body ?? {}),
    onMutate: async ({ taskId }) => {
      const key = [...tasksCacheKey(view, showCompleted)];
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ items: Task[]; total: number }>(key);
      if (previous) {
        const target = previous.items.find((t) => t.id === taskId);
        // Recurring tasks usually roll due forward instead of completing.
        if (!target?.recurrence) {
          queryClient.setQueryData(key, {
            ...previous,
            items: previous.items.map((t) =>
              t.id === taskId ? { ...t, is_completed: true } : t,
            ),
          });
        }
      }
      return { previous, key };
    },
    onError: (err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.key, context.previous);
      }
      if (!(err instanceof ApiError && err.code === "OPEN_CHILDREN")) {
        emitToast("Couldn't complete — reverted");
      }
    },
    onSuccess: (data, { taskId, undoTaskIds, body }) => {
      if (data.recurrence_advanced) {
        push({
          type: "recurrence_advance",
          taskId,
          previousDueAt: data.previous_due_at ?? null,
        });
      } else if (body?.bulk_children && undoTaskIds && undoTaskIds.length > 1) {
        push({ type: "bulk_complete", taskIds: undoTaskIds });
      } else {
        push({ type: "complete", taskId });
      }
    },
    onSettled: invalidateTasks,
  });

  const uncompleteMutation = useMutation({
    mutationFn: uncompleteTask,
    onMutate: async (taskId) => {
      const key = [...tasksCacheKey(view, showCompleted)];
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ items: Task[]; total: number }>(key);
      if (previous) {
        queryClient.setQueryData(key, {
          ...previous,
          items: previous.items.map((t) =>
            t.id === taskId ? { ...t, is_completed: false } : t,
          ),
        });
      }
      return { previous, key };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.key, context.previous);
      }
      emitToast("Couldn't uncomplete — reverted");
    },
    onSuccess: (_data, taskId) => {
      push({ type: "uncomplete", taskId });
    },
    onSettled: invalidateTasks,
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

  const scrollToTask = (taskId: string) => {
    rowRefs.current.get(taskId)?.scrollIntoView({ block: "nearest" });
  };

  useEffect(() => {
    if (focusedTaskId && !tasks.some((t) => t.id === focusedTaskId)) {
      setFocusedTaskId(tasks[0]?.id ?? null);
    }
  }, [tasks, focusedTaskId]);

  const handleReorderTask = (task: Task, direction: "up" | "down") => {
    const siblings = getTaskSiblings(task);
    const items = buildReorderSwap(siblings, task.id, direction);
    if (items) reorderTasksMutation.mutate({ items });
  };

  const handleReorderSection = (section: Section, direction: "up" | "down") => {
    const items = buildReorderSwap(sections, section.id, direction);
    if (items) reorderSectionsMutation.mutate({ items });
  };

  const handleToggleComplete = useCallback(async (task: Task) => {
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
  }, [completeMutation, uncompleteMutation]);

  useEffect(() => {
    const isInteractiveTarget = (target: EventTarget | null) => {
      if (!(target instanceof HTMLElement)) return false;
      return Boolean(target.closest("input, textarea, button, select"));
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (isInteractiveTarget(e.target)) return;
      if (document.querySelector(".modal-backdrop")) return;
      if (tasks.length === 0) return;

      const currentIndex = focusedTaskId
        ? tasks.findIndex((t) => t.id === focusedTaskId)
        : -1;

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        const nextIndex =
          currentIndex < 0 ? 0 : Math.min(currentIndex + 1, tasks.length - 1);
        const nextId = tasks[nextIndex].id;
        setFocusedTaskId(nextId);
        scrollToTask(nextId);
        return;
      }

      if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        const nextIndex =
          currentIndex < 0 ? tasks.length - 1 : Math.max(currentIndex - 1, 0);
        const nextId = tasks[nextIndex].id;
        setFocusedTaskId(nextId);
        scrollToTask(nextId);
        return;
      }

      if (e.key === "Enter" && focusedTaskId) {
        e.preventDefault();
        onSelectTask(focusedTaskId);
        return;
      }

      if ((e.key === "x" || e.key === "X" || e.key === " ") && focusedTaskId) {
        e.preventDefault();
        const task = tasks.find((t) => t.id === focusedTaskId);
        if (task) void handleToggleComplete(task);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [tasks, focusedTaskId, onSelectTask, handleToggleComplete]);

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
    setFocusedTaskId(task.id);
    onSelectTask(task.id);
  };

  const heading =
    view.type === "project"
      ? (projectTitle ?? "Project")
      : view.type === "epic"
        ? (projectTitle ?? "Epic")
        : view.type === "inbox"
          ? "Inbox"
          : view.type === "today"
            ? "Today"
            : view.type === "label"
              ? (labelsById.get(view.labelId)?.name ?? "Label")
              : "Upcoming";

  return (
    <div className="task-list-layout">
      <div className="task-list-pane">
        <header className="pane-header">
          <h1>{heading}</h1>
          <div className="pane-header-actions">
            <label className="show-completed-toggle">
              <input
                type="checkbox"
                checked={showCompleted}
                onChange={(e) => setShowCompletedPersisted(e.target.checked)}
              />
              <span>Show completed</span>
            </label>
            {view.type === "project" && <CreateSectionForm projectId={view.projectId} />}
          </div>
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
              ref={(el) => {
                if (el) rowRefs.current.set(task.id, el);
                else rowRefs.current.delete(task.id);
              }}
              className={`task-row${task.is_completed ? " completed" : ""}${selectedTaskId === task.id ? " selected" : ""}${focusedTaskId === task.id ? " focused" : ""}`}
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
              {(task.plan_name || task.plan_id) && (
                <span className="plan-badge">
                  Plan {task.plan_name ?? planNameById.get(task.plan_id!) ?? "…"}
                </span>
              )}
              {task.soft_target_at && (
                <span className="soft-target-badge">Soft {formatDue(task.soft_target_at)}</span>
              )}
              {task.deadline_at && (
                <span className="deadline-badge">Deadline {formatDue(task.deadline_at)}</span>
              )}
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

        {view.type !== "epic" && (
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
        )}
        {view.type === "epic" && (
          <p className="muted small epic-add-hint">
            Open a project under this epic to add tasks. This view lists tasks across linked projects.
          </p>
        )}

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
            const parentId = pendingComplete.taskId;
            void (async () => {
              const childIds = await fetchOpenDescendantIds(parentId);
              completeMutation.mutate(
                {
                  taskId: parentId,
                  body: { bulk_children: true },
                  undoTaskIds: [parentId, ...childIds],
                },
                { onSuccess: () => setPendingComplete(null) },
              );
            })();
          }}
        />

        <EditSectionForm section={editingSection} onClose={() => setEditingSection(null)} />
      </div>
    </div>
  );
}
