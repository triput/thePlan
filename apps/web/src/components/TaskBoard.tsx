import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  fetchLabels,
  fetchPlans,
  fetchProjects,
  fetchScheduledBlocks,
  fetchTasks,
  transitionTaskWorkflow,
  type Label,
  type Task,
  type TaskBoardColumnId,
} from "../api";
import { PRIORITY_COLORS } from "../colors";
import { fetchOpenDescendantIds, useUndoStack } from "../undoStack";
import { CompleteDialog } from "./CompleteDialog";
import { Modal } from "./Modal";
import { emitToast } from "./ToastHost";
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
import { readBoardRootsOnly, writeBoardRootsOnly } from "../taskPresentation";

interface TaskBoardProps {
  view: ViewSelection;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string | null) => void;
}

interface PendingComplete {
  taskId: string;
  taskTitle: string;
  openCount: number;
  expectedRevision: number;
}

interface PendingWaitingMove {
  task: Task;
  note: string;
}

const OPEN_COLUMNS: { id: TaskBoardColumnId; label: string }[] = [
  { id: "ready", label: "Ready" },
  { id: "in_progress", label: "In progress" },
  { id: "waiting", label: "Waiting" },
];

const DONE_COLUMN: TaskBoardColumnId = "done";
const OPEN_FETCH_LIMIT = 200;
const DONE_PAGE_SIZE = 30;

type OpenColumnId = "ready" | "in_progress" | "waiting";

type ColumnTasks = {
  items: Task[];
  total: number;
};

function isOverbookedStatus(status: string): boolean {
  return status === "overbooked";
}

function boardOpenQueryKey(view: ViewSelection, column: TaskBoardColumnId, rootsOnly: boolean) {
  return ["tasks", "board", "column", viewKey(view), column, rootsOnly ? "roots" : "all"] as const;
}

function boardDoneQueryKey(view: ViewSelection, offset: number) {
  return ["tasks", "board", "column", viewKey(view), DONE_COLUMN, offset] as const;
}

function buildListBaseParams(view: ViewSelection): Record<string, string | number | boolean> {
  if (view.type === "inbox") {
    return { inbox: true, limit: OPEN_FETCH_LIMIT, board_order: true };
  }
  if (view.type === "project") {
    return { project_id: view.projectId, limit: OPEN_FETCH_LIMIT, board_order: true };
  }
  if (view.type === "epic") {
    return { epic_id: view.epicId, limit: OPEN_FETCH_LIMIT, board_order: true };
  }
  if (view.type === "label") {
    return { label_id: view.labelId, limit: OPEN_FETCH_LIMIT, board_order: true };
  }
  return { limit: OPEN_FETCH_LIMIT, board_order: true };
}

function applyViewFilters(
  items: Task[],
  view: ViewSelection,
  scheduledIds: Set<string>,
): Task[] {
  let filtered = items;
  if (view.type === "label") {
    filtered = filtered.filter((t) => t.label_ids.includes(view.labelId));
  }
  if (view.type === "today") {
    filtered = filtered.filter((t) => isToday(t.due_at) || scheduledIds.has(t.id));
  } else if (view.type === "upcoming") {
    filtered = filtered.filter((t) => isUpcoming(t.due_at) || scheduledIds.has(t.id));
  }
  return filtered;
}

function columnForOpenTask(task: Task): TaskBoardColumnId {
  if (task.is_completed) return DONE_COLUMN;
  return task.workflow_state;
}

function groupOpenTasks(tasks: Task[]): Record<TaskBoardColumnId, Task[]> {
  const groups: Record<TaskBoardColumnId, Task[]> = {
    ready: [],
    in_progress: [],
    waiting: [],
    done: [],
  };
  for (const task of tasks) {
    if (task.is_completed) continue;
    groups[columnForOpenTask(task)].push(task);
  }
  for (const col of OPEN_COLUMNS) {
    groups[col.id].sort((a, b) => {
      if (a.board_rank !== b.board_rank) return a.board_rank - b.board_rank;
      return a.id.localeCompare(b.id);
    });
  }
  return groups;
}

export function TaskBoard({ view, selectedTaskId, onSelectTask }: TaskBoardProps) {
  const queryClient = useQueryClient();
  const { push } = useUndoStack();
  const [rootsOnly, setRootsOnly] = useState(readBoardRootsOnly);
  const [doneOffset, setDoneOffset] = useState(0);
  const [doneItems, setDoneItems] = useState<Task[]>([]);
  const [pendingComplete, setPendingComplete] = useState<PendingComplete | null>(null);
  const [pendingWaiting, setPendingWaiting] = useState<PendingWaitingMove | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<TaskBoardColumnId | null>(null);

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

  const smartFilter = view.type === "today" || view.type === "upcoming";

  const blocksQuery = useQuery({
    queryKey: ["scheduled-blocks", viewKey(view), smartRange?.start.toISOString()],
    queryFn: () =>
      fetchScheduledBlocks({
        start: smartRange!.start.toISOString(),
        end: smartRange!.end.toISOString(),
      }),
    enabled: smartFilter,
  });

  const scheduledIds = useMemo(() => {
    if (view.type === "today") {
      return new Set(
        (blocksQuery.data?.items ?? [])
          .filter((b) => rangeOverlapsLocalDay(b.start_time, b.end_time, new Date()))
          .map((b) => b.task_id),
      );
    }
    if (view.type === "upcoming") {
      return new Set((blocksQuery.data?.items ?? []).map((b) => b.task_id));
    }
    return new Set<string>();
  }, [blocksQuery.data, view.type]);

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

  const plansQuery = useQuery({ queryKey: ["plans"], queryFn: fetchPlans });
  const planNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const plan of plansQuery.data ?? []) {
      map.set(plan.id, plan.name);
    }
    return map;
  }, [plansQuery.data]);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects({ limit: 200 }),
  });
  const projectById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of projectsQuery.data?.items ?? []) {
      map.set(p.id, p.title);
    }
    return map;
  }, [projectsQuery.data]);

  const showProjectContext = view.type !== "project";

  const openBundleQuery = useQuery({
    queryKey: ["tasks", "board", "open-bundle", viewKey(view)],
    enabled: smartFilter,
    queryFn: async () => {
      const result = await fetchTasks({
        ...buildListBaseParams(view),
        is_completed: false,
      });
      return result;
    },
  });

  const columnQueries = useQueries({
    queries: smartFilter
      ? []
      : OPEN_COLUMNS.map((col) => ({
          queryKey: boardOpenQueryKey(view, col.id, rootsOnly),
          queryFn: async () => {
            const result = await fetchTasks({
              ...buildListBaseParams(view),
              workflow: col.id,
              is_completed: false,
            });
            return { items: result.items, total: result.total };
          },
        })),
  });

  const doneQuery = useQuery({
    queryKey: boardDoneQueryKey(view, doneOffset),
    queryFn: async () => {
      const result = await fetchTasks({
        ...buildListBaseParams(view),
        workflow: DONE_COLUMN,
        limit: DONE_PAGE_SIZE,
        offset: doneOffset,
      });
      let items = result.items;
      if (view.type === "label") {
        items = items.filter((t) => t.label_ids.includes(view.labelId));
      }
      if (smartFilter) {
        items = applyViewFilters(items, view, scheduledIds);
      }
      return { items, total: result.total };
    },
  });

  const mergedOpenFromBundle = useMemo(() => {
    if (!smartFilter || !openBundleQuery.data) return null;
    let items = applyViewFilters(openBundleQuery.data.items, view, scheduledIds);
    if (rootsOnly) {
      items = items.filter((t) => t.parent_task_id === null);
    }
    return groupOpenTasks(items);
  }, [smartFilter, openBundleQuery.data, view, scheduledIds, rootsOnly]);

  const openByColumn = useMemo(() => {
    if (smartFilter && mergedOpenFromBundle) {
      return mergedOpenFromBundle;
    }
    const groups: Record<TaskBoardColumnId, Task[]> = {
      ready: [],
      in_progress: [],
      waiting: [],
      done: [],
    };
    OPEN_COLUMNS.forEach((col, index) => {
      const data = columnQueries[index]?.data as ColumnTasks | undefined;
      let items = data?.items ?? [];
      if (rootsOnly) {
        items = items.filter((t) => t.parent_task_id === null);
      }
      groups[col.id] = items;
    });
    return groups;
  }, [smartFilter, mergedOpenFromBundle, columnQueries, rootsOnly]);

  const openColumnTotals = useMemo(() => {
    if (smartFilter && mergedOpenFromBundle) {
      return {
        ready: mergedOpenFromBundle.ready.length,
        in_progress: mergedOpenFromBundle.in_progress.length,
        waiting: mergedOpenFromBundle.waiting.length,
      };
    }
    const totals: Record<OpenColumnId, number> = {
      ready: 0,
      in_progress: 0,
      waiting: 0,
    };
    OPEN_COLUMNS.forEach((col, index) => {
      const data = columnQueries[index]?.data as ColumnTasks | undefined;
      totals[col.id as OpenColumnId] = data?.total ?? 0;
    });
    return totals;
  }, [smartFilter, mergedOpenFromBundle, columnQueries]);

  const wipCount = openColumnTotals.in_progress + openColumnTotals.waiting;

  const allTasksById = useMemo(() => {
    const map = new Map<string, Task>();
    for (const col of OPEN_COLUMNS) {
      for (const task of openByColumn[col.id]) {
        map.set(task.id, task);
      }
    }
    for (const task of doneItems) {
      map.set(task.id, task);
    }
    for (const task of doneQuery.data?.items ?? []) {
      map.set(task.id, task);
    }
    if (openBundleQuery.data) {
      for (const task of openBundleQuery.data.items) {
        map.set(task.id, task);
      }
    }
    return map;
  }, [openByColumn, doneItems, doneQuery.data, openBundleQuery.data]);

  const doneTotal = doneQuery.data?.total ?? 0;
  const doneLoadedCount = doneItems.length;

  useEffect(() => {
    setDoneOffset(0);
    setDoneItems([]);
  }, [viewKey(view)]);

  useEffect(() => {
    if (!doneQuery.data) return;
    setDoneItems((prev) => {
      if (doneOffset === 0) return doneQuery.data.items;
      const seen = new Set(prev.map((t) => t.id));
      const appended = doneQuery.data.items.filter((t) => !seen.has(t.id));
      return [...prev, ...appended];
    });
  }, [doneQuery.data, doneOffset]);

  const invalidateBoard = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["tasks", "board"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  }, [queryClient]);

  const moveMutation = useMutation({
    mutationFn: ({
      taskId,
      body,
    }: {
      taskId: string;
      body: Parameters<typeof transitionTaskWorkflow>[1];
      taskTitle?: string;
    }) => transitionTaskWorkflow(taskId, body),
    onMutate: async ({ taskId, body }) => {
      await queryClient.cancelQueries({ queryKey: ["tasks", "board"] });
      const snapshots = queryClient.getQueriesData<{ items: Task[]; total: number }>({
        queryKey: ["tasks", "board"],
      });
      return { snapshots, taskId, targetColumn: body.column };
    },
    onError: (err, _vars, context) => {
      if (context?.snapshots) {
        for (const [key, data] of context.snapshots) {
          queryClient.setQueryData(key, data);
        }
      }
      if (err instanceof ApiError && err.code === "BOARD_REVISION_CONFLICT") {
        emitToast("Board changed elsewhere — refreshed");
        invalidateBoard();
        return;
      }
      if (err instanceof ApiError && err.code === "OPEN_CHILDREN") {
        return;
      }
      emitToast("Couldn't move card — reverted");
    },
    onSuccess: (data, { taskId, body }) => {
      if (data.recurrence_advanced) {
        emitToast("Recurring task advanced to next occurrence");
        push({
          type: "recurrence_advance",
          taskId,
          previousDueAt: data.previous_due_at ?? null,
        });
      } else if (body.column === DONE_COLUMN) {
        push({ type: "complete", taskId });
      }
      invalidateBoard();
      setDoneOffset(0);
      setDoneItems([]);
    },
  });

  const runMove = useCallback(
    async (
      task: Task,
      column: TaskBoardColumnId,
      opts?: {
        waiting_note?: string | null;
        insert_before_id?: string;
        insert_after_id?: string;
        bulk_children?: boolean;
        force_parent_only?: boolean;
      },
    ) => {
      const fromColumn = columnForOpenTask(task);
      if (column === fromColumn && !opts?.insert_before_id && !opts?.insert_after_id) {
        return;
      }
      try {
        await moveMutation.mutateAsync({
          taskId: task.id,
          taskTitle: task.title,
          body: {
            column,
            expected_revision: task.board_revision,
            waiting_note: opts?.waiting_note,
            insert_before_id: opts?.insert_before_id,
            insert_after_id: opts?.insert_after_id,
            bulk_children: opts?.bulk_children,
            force_parent_only: opts?.force_parent_only,
          },
        });
      } catch (err) {
        if (err instanceof ApiError && err.code === "OPEN_CHILDREN" && column === DONE_COLUMN) {
          setPendingComplete({
            taskId: task.id,
            taskTitle: task.title,
            openCount: err.openCount ?? task.open_subtask_count,
            expectedRevision: task.board_revision,
          });
        }
      }
    },
    [moveMutation],
  );

  const handleMoveSelect = (task: Task, value: string) => {
    if (!value) return;
    if (value === "waiting") {
      setPendingWaiting({ task, note: task.waiting_note ?? "" });
      return;
    }
    void runMove(task, value as TaskBoardColumnId);
  };

  const parentTitle = (task: Task) => {
    if (!task.parent_task_id) return null;
    return allTasksById.get(task.parent_task_id)?.title ?? "Subtask";
  };

  const loading =
    (smartFilter ? openBundleQuery.isLoading : columnQueries.some((q) => q.isLoading)) ||
    doneQuery.isLoading;

  const loadMoreDone = () => {
    setDoneOffset((prev) => prev + DONE_PAGE_SIZE);
  };

  const onColumnDragOver = (e: React.DragEvent, column: TaskBoardColumnId) => {
    e.preventDefault();
    setDragOverColumn(column);
  };

  const onColumnDrop = (e: React.DragEvent, column: TaskBoardColumnId) => {
    e.preventDefault();
    setDragOverColumn(null);
    const raw = e.dataTransfer.getData("application/x-theplan-task-id");
    if (!raw) return;
    const task = allTasksById.get(raw);
    if (!task) return;
    if (column === "waiting") {
      setPendingWaiting({ task, note: task.waiting_note ?? "" });
      return;
    }
    void runMove(task, column);
  };

  const onCardDragStart = (e: React.DragEvent, taskId: string) => {
    e.dataTransfer.setData("application/x-theplan-task-id", taskId);
    e.dataTransfer.effectAllowed = "move";
  };

  const renderCard = (task: Task) => {
    const parent = parentTitle(task);
    const projectLabel =
      showProjectContext && task.project_id
        ? projectById.get(task.project_id) ?? "Project"
        : null;
    return (
      <article
        key={task.id}
        className={`task-board-card${selectedTaskId === task.id ? " selected" : ""}`}
        draggable
        onDragStart={(e) => onCardDragStart(e, task.id)}
        onClick={() => onSelectTask(task.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelectTask(task.id);
          }
        }}
        tabIndex={0}
        role="button"
        aria-label={task.title}
      >
        {parent && <span className="task-board-breadcrumb">↳ {parent}</span>}
        <span className="task-board-card-title">{task.title}</span>
        {projectLabel && <span className="task-board-breadcrumb">{projectLabel}</span>}
        {task.waiting_note && (
          <span className="task-board-waiting-note">{task.waiting_note}</span>
        )}
        <div className="task-board-card-meta">
          {task.priority !== "p4" && (
            <span className="priority-badge" style={{ color: PRIORITY_COLORS[task.priority] }}>
              {task.priority.toUpperCase()}
            </span>
          )}
          {task.due_at && <span className="due-badge">{formatDue(task.due_at)}</span>}
          {task.deadline_at && (
            <span className="deadline-badge">Deadline {formatDue(task.deadline_at)}</span>
          )}
          {(task.plan_name || task.plan_id) && (
            <span className="plan-badge">
              Plan {task.plan_name ?? planNameById.get(task.plan_id!) ?? "…"}
            </span>
          )}
          {isOverbookedStatus(task.status) && (
            <span className="overbooked-badge">Overbooked</span>
          )}
          {task.estimated_duration_minutes > 0 && (
            <span className="duration-badge">{formatDuration(task.estimated_duration_minutes)}</span>
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
          {task.workflow_state === "waiting" && task.schedule_style !== "manual" && (
            <span className="task-board-sched-hint" title="Waiting does not disable scheduling">
              Schedulable
            </span>
          )}
          {task.schedule_style === "manual" && (
            <span className="task-board-sched-hint">Manual / backlog</span>
          )}
        </div>
        <div className="task-board-card-actions">
          <select
            className="task-board-move-select"
            value=""
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => {
              e.stopPropagation();
              handleMoveSelect(task, e.target.value);
              e.target.value = "";
            }}
            aria-label={`Move ${task.title} to column`}
          >
            <option value="">Move to…</option>
            {OPEN_COLUMNS.filter((c) => !task.is_completed && c.id !== columnForOpenTask(task)).map(
              (c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ),
            )}
            {task.is_completed &&
              OPEN_COLUMNS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            {!task.is_completed && columnForOpenTask(task) !== DONE_COLUMN && (
              <option value={DONE_COLUMN}>Done</option>
            )}
          </select>
        </div>
      </article>
    );
  };

  const renderOpenColumn = (col: (typeof OPEN_COLUMNS)[number]) => {
    const items = openByColumn[col.id];
    const total = rootsOnly ? items.length : openColumnTotals[col.id as OpenColumnId];
    return (
      <section
        key={col.id}
        className="task-board-column"
        aria-label={`${col.label} column`}
      >
        <header className="task-board-column-header">
          <h2 className="task-board-column-title">{col.label}</h2>
          <span className="task-board-column-count">{total}</span>
        </header>
        <div
          className={`task-board-column-body${dragOverColumn === col.id ? " drag-over" : ""}`}
          onDragOver={(e) => onColumnDragOver(e, col.id)}
          onDragLeave={() => setDragOverColumn(null)}
          onDrop={(e) => onColumnDrop(e, col.id)}
        >
          {items.length === 0 && !loading && (
            <p className="muted small">No tasks</p>
          )}
          {items.map(renderCard)}
        </div>
      </section>
    );
  };

  return (
    <div className="task-board-wrap">
      <div className="task-board-toolbar">
        <p className="task-board-wip-summary" role="status">
          WIP (In progress + Waiting): {wipCount} task{wipCount === 1 ? "" : "s"}
        </p>
        <label className="show-completed-toggle">
          <input
            type="checkbox"
            checked={rootsOnly}
            onChange={(e) => {
              setRootsOnly(e.target.checked);
              writeBoardRootsOnly(e.target.checked);
            }}
          />
          <span>Roots only</span>
        </label>
      </div>

      {loading && <p className="muted">Loading board…</p>}

      <div className="task-board-columns">
        {OPEN_COLUMNS.map(renderOpenColumn)}
        <section className="task-board-column" aria-label="Done column">
          <header className="task-board-column-header">
            <h2 className="task-board-column-title">Done</h2>
            <span className="task-board-column-count">{doneTotal}</span>
          </header>
          <div
            className={`task-board-column-body${dragOverColumn === DONE_COLUMN ? " drag-over" : ""}`}
            onDragOver={(e) => onColumnDragOver(e, DONE_COLUMN)}
            onDragLeave={() => setDragOverColumn(null)}
            onDrop={(e) => onColumnDrop(e, DONE_COLUMN)}
          >
            {doneItems.length === 0 && !loading && (
              <p className="muted small">No completed tasks loaded</p>
            )}
            {doneItems.map(renderCard)}
            {doneLoadedCount < doneTotal && (
              <button
                type="button"
                className="btn secondary small task-board-load-more"
                onClick={loadMoreDone}
                disabled={doneQuery.isFetching}
              >
                {doneQuery.isFetching ? "Loading…" : "Load more"}
              </button>
            )}
          </div>
        </section>
      </div>

      <CompleteDialog
        open={pendingComplete !== null}
        taskTitle={pendingComplete?.taskTitle ?? ""}
        openCount={pendingComplete?.openCount ?? 0}
        pending={moveMutation.isPending}
        onClose={() => setPendingComplete(null)}
        onParentOnly={() => {
          if (!pendingComplete) return;
          const task = allTasksById.get(pendingComplete.taskId);
          if (!task) return;
          void runMove(task, DONE_COLUMN, { force_parent_only: true }).then(() =>
            setPendingComplete(null),
          );
        }}
        onBulkChildren={() => {
          if (!pendingComplete) return;
          const task = allTasksById.get(pendingComplete.taskId);
          if (!task) return;
          void (async () => {
            const childIds = await fetchOpenDescendantIds(pendingComplete.taskId);
            await runMove(task, DONE_COLUMN, { bulk_children: true });
            if (childIds.length > 0) {
              push({ type: "bulk_complete", taskIds: [pendingComplete.taskId, ...childIds] });
            }
            setPendingComplete(null);
          })();
        }}
      />

      <Modal
        open={pendingWaiting !== null}
        title="Move to Waiting"
        onClose={() => setPendingWaiting(null)}
      >
        {pendingWaiting && (
          <>
            <p className="dialog-text muted small">
              Optional note for <strong>{pendingWaiting.task.title}</strong> (what you&apos;re
              waiting on).
            </p>
            <textarea
              className="task-board-waiting-input"
              rows={3}
              maxLength={500}
              value={pendingWaiting.note}
              onChange={(e) =>
                setPendingWaiting({ ...pendingWaiting, note: e.target.value })
              }
              placeholder="e.g. Reply from vendor"
            />
            <div className="form-actions stacked">
              <button
                type="button"
                className="btn primary"
                disabled={moveMutation.isPending}
                onClick={() => {
                  void runMove(pendingWaiting.task, "waiting", {
                    waiting_note: pendingWaiting.note.trim() || null,
                  }).then(() => setPendingWaiting(null));
                }}
              >
                Move to Waiting
              </button>
              <button
                type="button"
                className="btn ghost"
                onClick={() => setPendingWaiting(null)}
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
