// ==============================================================================
//  File: apps/web/src/components/TaskBoard.tsx
//  Description: Kanban board including saved-view queries, load-more, and WIP counts (F2/F7).
//  Component: Task Board
//  Version: 1.0
//  Created: 2026-08-27
//  Last Update: 2026-10-10
// ==============================================================================

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  fetchEpics,
  fetchLabels,
  fetchPlans,
  fetchProjects,
  fetchScheduledBlocks,
  fetchTasks,
  queryViewTasks,
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
import { mergeAccumPage } from "../boardAccum";
import {
  ownerWideBoardView,
  readBoardRootsOnly,
  readBoardWorkFilters,
  writeBoardRootsOnly,
  writeBoardWorkFilters,
  type BoardWorkFilters,
} from "../taskPresentation";

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

type DropInsertHint = { insert_before_id?: string; insert_after_id?: string };

interface PendingWaitingMove {
  task: Task;
  note: string;
  hints: DropInsertHint;
}

const OPEN_COLUMNS: { id: TaskBoardColumnId; label: string }[] = [
  { id: "ready", label: "Ready" },
  { id: "in_progress", label: "In progress" },
  { id: "waiting", label: "Waiting" },
];

const DONE_COLUMN: TaskBoardColumnId = "done";
const OPEN_PAGE_SIZE = 50;
const DONE_PAGE_SIZE = 30;
const SAVED_BOARD_PAGE_SIZE = 500;

/** Default GET /tasks excludes archived project/epic tasks; explicit project_id may still include them. */

type OpenColumnId = "ready" | "in_progress" | "waiting";

type ColumnTasks = {
  items: Task[];
  total: number;
};

function isOverbookedStatus(status: string): boolean {
  return status === "overbooked";
}

function boardOpenQueryKey(
  view: ViewSelection,
  column: TaskBoardColumnId,
  offset: number,
  workFilters: BoardWorkFilters,
) {
  return [
    "tasks",
    "board",
    "column",
    viewKey(view),
    column,
    offset,
    workFilters.projectId ?? "",
    workFilters.epicId ?? "",
  ] as const;
}

function boardSmartOpenQueryKey(
  view: ViewSelection,
  offset: number,
  workFilters: BoardWorkFilters,
  dueKey: string,
) {
  return ["tasks", "board", "smart-open", viewKey(view), offset, workFilters.projectId ?? "", workFilters.epicId ?? "", dueKey] as const;
}

function boardDoneQueryKey(
  view: ViewSelection,
  offset: number,
  workFilters: BoardWorkFilters,
  dueKey: string,
) {
  return ["tasks", "board", "column", viewKey(view), DONE_COLUMN, offset, workFilters.projectId ?? "", workFilters.epicId ?? "", dueKey] as const;
}

function buildScopeParams(
  view: ViewSelection,
  workFilters: BoardWorkFilters,
): Record<string, string | number | boolean> {
  const base: Record<string, string | number | boolean> = { board_order: true };
  if (view.type === "project") {
    return { ...base, project_id: view.projectId };
  }
  if (view.type === "epic") {
    return { ...base, epic_id: view.epicId };
  }
  if (view.type === "label") {
    return { ...base, label_id: view.labelId };
  }
  if (ownerWideBoardView(view)) {
    if (workFilters.projectId) {
      return { ...base, project_id: workFilters.projectId };
    }
    if (workFilters.epicId) {
      return { ...base, epic_id: workFilters.epicId };
    }
    if (view.type === "inbox") {
      return { ...base, inbox: true };
    }
    // work / today / upcoming with All filters: full owner scope (no inbox=true)
    return base;
  }
  return base;
}

function dueRangeParams(
  view: ViewSelection,
  smartRange: { start: Date; end: Date } | null,
): { due_from?: string; due_to?: string } {
  if (!smartRange || (view.type !== "today" && view.type !== "upcoming")) {
    return {};
  }
  return {
    due_from: smartRange.start.toISOString(),
    due_to: smartRange.end.toISOString(),
  };
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
  const [workFilters, setWorkFilters] = useState<BoardWorkFilters>(readBoardWorkFilters);
  const [openOffsets, setOpenOffsets] = useState<Record<OpenColumnId, number>>({
    ready: 0,
    in_progress: 0,
    waiting: 0,
  });
  const [openAccum, setOpenAccum] = useState<Record<OpenColumnId, Task[]>>({
    ready: [],
    in_progress: [],
    waiting: [],
  });
  const [openServerTotals, setOpenServerTotals] = useState<Record<OpenColumnId, number>>({
    ready: 0,
    in_progress: 0,
    waiting: 0,
  });
  const [smartOpenOffset, setSmartOpenOffset] = useState(0);
  const [smartOpenAccum, setSmartOpenAccum] = useState<Task[]>([]);
  const [smartOpenTotal, setSmartOpenTotal] = useState(0);
  const [doneRawOffset, setDoneRawOffset] = useState(0);
  const [doneItems, setDoneItems] = useState<Task[]>([]);
  const [doneRawTotal, setDoneRawTotal] = useState(0);
  const [accumResetGen, setAccumResetGen] = useState(0);
  const [savedViewOffset, setSavedViewOffset] = useState(0);
  const [savedViewAccum, setSavedViewAccum] = useState<Task[]>([]);
  const [savedViewTotal, setSavedViewTotal] = useState(0);
  const [pendingComplete, setPendingComplete] = useState<PendingComplete | null>(null);
  const [pendingWaiting, setPendingWaiting] = useState<PendingWaitingMove | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<TaskBoardColumnId | null>(null);
  const [dragOverCard, setDragOverCard] = useState<{
    taskId: string;
    edge: "before" | "after";
  } | null>(null);
  const [draggingTaskId, setDraggingTaskId] = useState<string | null>(null);

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

  const isSavedView = view.type === "saved";
  const smartFilter = !isSavedView && (view.type === "today" || view.type === "upcoming");
  const dueKey = smartRange ? `${smartRange.start.toISOString()}/${smartRange.end.toISOString()}` : "";
  const dueParams = dueRangeParams(view, smartRange);
  const scopeParams = buildScopeParams(view, workFilters);
  const showWorkFilters = ownerWideBoardView(view);

  const epicsQuery = useQuery({
    queryKey: ["epics", "board-filters"],
    queryFn: () => fetchEpics({ archived: false, limit: 200 }),
    enabled: showWorkFilters,
  });

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
  const activeProjects = useMemo(
    () => (projectsQuery.data?.items ?? []).filter((p) => !p.is_archived),
    [projectsQuery.data],
  );
  const projectById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of projectsQuery.data?.items ?? []) {
      map.set(p.id, p.title);
    }
    return map;
  }, [projectsQuery.data]);

  const showProjectContext = view.type !== "project" && !isSavedView;

  const savedViewBoardQuery = useQuery({
    queryKey: [
      "views",
      isSavedView && view.type === "saved" ? view.id : "",
      "tasks",
      "board",
      savedViewOffset,
    ],
    enabled: isSavedView && view.type === "saved",
    queryFn: () => {
      if (view.type !== "saved") throw new Error("Saved view required");
      return queryViewTasks(view.id, {
        limit: SAVED_BOARD_PAGE_SIZE,
        offset: savedViewOffset,
        board_order: true,
      });
    },
  });

  const scheduledOpenIds = useMemo(() => {
    if (!smartFilter) return [] as string[];
    return [...scheduledIds].filter(Boolean);
  }, [smartFilter, scheduledIds]);

  const scheduledOpenQuery = useQuery({
    queryKey: [
      "tasks",
      "board",
      "scheduled-open",
      viewKey(view),
      workFilters.projectId ?? "",
      workFilters.epicId ?? "",
      scheduledOpenIds.join(","),
    ],
    enabled: smartFilter && scheduledOpenIds.length > 0,
    queryFn: async () => {
      const result = await fetchTasks({
        ...scopeParams,
        ids: scheduledOpenIds,
        is_completed: false,
        limit: Math.min(scheduledOpenIds.length, 200),
        board_order: true,
      });
      return result.items;
    },
  });

  const smartOpenQuery = useQuery({
    queryKey: boardSmartOpenQueryKey(view, smartOpenOffset, workFilters, dueKey),
    enabled: smartFilter,
    queryFn: async () => {
      const result = await fetchTasks({
        ...scopeParams,
        ...dueParams,
        is_completed: false,
        limit: OPEN_PAGE_SIZE,
        offset: smartOpenOffset,
      });
      return { items: result.items, total: result.total };
    },
  });

  const columnQueries = useQueries({
    queries: smartFilter || isSavedView
      ? []
      : OPEN_COLUMNS.map((col) => ({
          queryKey: boardOpenQueryKey(view, col.id, openOffsets[col.id as OpenColumnId], workFilters),
          queryFn: async () => {
            const offset = openOffsets[col.id as OpenColumnId];
            const result = await fetchTasks({
              ...scopeParams,
              workflow: col.id,
              is_completed: false,
              limit: OPEN_PAGE_SIZE,
              offset,
            });
            return { items: result.items, total: result.total, offset };
          },
        })),
  });

  const doneQuery = useQuery({
    queryKey: boardDoneQueryKey(view, doneRawOffset, workFilters, dueKey),
    enabled: !isSavedView,
    queryFn: async () => {
      const result = await fetchTasks({
        ...scopeParams,
        ...(smartFilter ? dueParams : {}),
        workflow: DONE_COLUMN,
        limit: DONE_PAGE_SIZE,
        offset: doneRawOffset,
      });
      let items = result.items;
      if (view.type === "label") {
        items = items.filter((t) => t.label_ids.includes(view.labelId));
      }
      if (smartFilter) {
        items = applyViewFilters(items, view, scheduledIds);
      }
      return { items, rawItems: result.items, total: result.total };
    },
  });

  const boardResetKey = `${viewKey(view)}|${workFilters.projectId ?? ""}|${workFilters.epicId ?? ""}|${dueKey}`;

  useEffect(() => {
    setOpenOffsets({ ready: 0, in_progress: 0, waiting: 0 });
    setOpenAccum({ ready: [], in_progress: [], waiting: [] });
    setOpenServerTotals({ ready: 0, in_progress: 0, waiting: 0 });
    setSmartOpenOffset(0);
    setSmartOpenAccum([]);
    setSmartOpenTotal(0);
    setDoneRawOffset(0);
    setDoneItems([]);
    setDoneRawTotal(0);
    setSavedViewOffset(0);
    setSavedViewAccum([]);
    setSavedViewTotal(0);
    setAccumResetGen((g) => g + 1);
  }, [boardResetKey]);

  useEffect(() => {
    if (!isSavedView || !savedViewBoardQuery.data) return;
    setSavedViewTotal(savedViewBoardQuery.data.total);
    setSavedViewAccum((prev) =>
      mergeAccumPage(prev, savedViewBoardQuery.data!.items, savedViewOffset),
    );
  }, [isSavedView, savedViewBoardQuery.data, savedViewOffset, accumResetGen]);

  useEffect(() => {
    if (!smartFilter || !smartOpenQuery.data) return;
    const { items, total } = smartOpenQuery.data;
    setSmartOpenTotal(total);
    setSmartOpenAccum((prev) => mergeAccumPage(prev, items, smartOpenOffset));
  }, [smartFilter, smartOpenQuery.data, smartOpenOffset, accumResetGen]);

  useEffect(() => {
    if (!doneQuery.data) return;
    setDoneRawTotal(doneQuery.data.total);
    setDoneItems((prev) => mergeAccumPage(prev, doneQuery.data.items, doneRawOffset));
  }, [doneQuery.data, doneRawOffset, accumResetGen]);

  const mergedSmartOpen = useMemo(() => {
    if (!smartFilter) return null;
    const byId = new Map<string, Task>();
    for (const task of smartOpenAccum) {
      byId.set(task.id, task);
    }
    for (const task of scheduledOpenQuery.data ?? []) {
      byId.set(task.id, task);
    }
    let items = applyViewFilters([...byId.values()], view, scheduledIds);
    if (rootsOnly) {
      items = items.filter((t) => t.parent_task_id === null);
    }
    return groupOpenTasks(items);
  }, [smartFilter, smartOpenAccum, scheduledOpenQuery.data, view, scheduledIds, rootsOnly]);

  const savedViewLoadedCount = isSavedView ? savedViewAccum.length : 0;
  const savedViewHasMore =
    isSavedView && savedViewLoadedCount < savedViewTotal;

  const savedViewGrouped = useMemo(() => {
    if (!isSavedView || savedViewAccum.length === 0) return null;
    let openItems = savedViewAccum.filter((t) => !t.is_completed);
    if (rootsOnly) {
      openItems = openItems.filter((t) => t.parent_task_id === null);
    }
    return groupOpenTasks(openItems);
  }, [isSavedView, savedViewAccum, rootsOnly]);

  const savedViewDoneItems = useMemo(() => {
    if (!isSavedView || savedViewAccum.length === 0) return [];
    let items = savedViewAccum.filter((t) => t.is_completed);
    if (rootsOnly) {
      items = items.filter((t) => t.parent_task_id === null);
    }
    return items;
  }, [isSavedView, savedViewAccum, rootsOnly]);

  const openByColumn = useMemo(() => {
    if (isSavedView && savedViewGrouped) {
      return savedViewGrouped;
    }
    if (smartFilter && mergedSmartOpen) {
      return mergedSmartOpen;
    }
    const groups: Record<TaskBoardColumnId, Task[]> = {
      ready: [],
      in_progress: [],
      waiting: [],
      done: [],
    };
    OPEN_COLUMNS.forEach((col) => {
      let items = openAccum[col.id as OpenColumnId] ?? [];
      if (rootsOnly) {
        items = items.filter((t) => t.parent_task_id === null);
      }
      groups[col.id] = items;
    });
    return groups;
  }, [isSavedView, savedViewGrouped, smartFilter, mergedSmartOpen, openAccum, rootsOnly]);

  const openColumnTotals = useMemo(() => {
    if (isSavedView && savedViewGrouped) {
      const suffix = savedViewHasMore ? "+" : "";
      return {
        ready: `${savedViewGrouped.ready.length}${suffix}`,
        in_progress: `${savedViewGrouped.in_progress.length}${suffix}`,
        waiting: `${savedViewGrouped.waiting.length}${suffix}`,
      };
    }
    if (smartFilter && mergedSmartOpen) {
      const smartHasMore = smartOpenOffset + OPEN_PAGE_SIZE < smartOpenTotal;
      const suffix = smartHasMore ? "+" : "";
      return {
        ready: `${mergedSmartOpen.ready.length}${suffix}`,
        in_progress: `${mergedSmartOpen.in_progress.length}${suffix}`,
        waiting: `${mergedSmartOpen.waiting.length}${suffix}`,
      };
    }
    const totals: Record<OpenColumnId, string | number> = {
      ready: openServerTotals.ready,
      in_progress: openServerTotals.in_progress,
      waiting: openServerTotals.waiting,
    };
    return totals;
  }, [
    isSavedView,
    savedViewGrouped,
    savedViewHasMore,
    smartFilter,
    mergedSmartOpen,
    openServerTotals,
    smartOpenOffset,
    smartOpenTotal,
  ]);

  const openColumnHasMore = useCallback(
    (colId: OpenColumnId): boolean => {
      if (isSavedView) {
        return savedViewHasMore;
      }
      if (smartFilter) {
        return smartOpenOffset + OPEN_PAGE_SIZE < smartOpenTotal;
      }
      const loaded = openAccum[colId].length;
      return loaded < openServerTotals[colId];
    },
    [
      isSavedView,
      savedViewHasMore,
      smartFilter,
      smartOpenOffset,
      smartOpenTotal,
      openAccum,
      openServerTotals,
    ],
  );

  const wipCount = useMemo(() => {
    if (isSavedView && savedViewGrouped) {
      return savedViewGrouped.in_progress.length + savedViewGrouped.waiting.length;
    }
    if (smartFilter && mergedSmartOpen) {
      return mergedSmartOpen.in_progress.length + mergedSmartOpen.waiting.length;
    }
    return openServerTotals.in_progress + openServerTotals.waiting;
  }, [isSavedView, savedViewGrouped, smartFilter, mergedSmartOpen, openServerTotals]);

  const doneColumnItems = isSavedView ? savedViewDoneItems : doneItems;

  const allTasksById = useMemo(() => {
    const map = new Map<string, Task>();
    for (const col of OPEN_COLUMNS) {
      for (const task of openByColumn[col.id]) {
        map.set(task.id, task);
      }
      for (const task of openAccum[col.id as OpenColumnId] ?? []) {
        map.set(task.id, task);
      }
    }
    for (const task of smartOpenAccum) {
      map.set(task.id, task);
    }
    for (const task of scheduledOpenQuery.data ?? []) {
      map.set(task.id, task);
    }
    for (const task of doneColumnItems) {
      map.set(task.id, task);
    }
    if (isSavedView) {
      for (const task of savedViewAccum) {
        map.set(task.id, task);
      }
    }
    return map;
  }, [
    openByColumn,
    openAccum,
    smartOpenAccum,
    scheduledOpenQuery.data,
    doneColumnItems,
    isSavedView,
    savedViewAccum,
  ]);

  const doneFilteredView = smartFilter || isSavedView;
  const doneHasMore = isSavedView
    ? savedViewHasMore
    : doneRawOffset + DONE_PAGE_SIZE < doneRawTotal;
  const doneDisplayTotal = isSavedView
    ? `${savedViewDoneItems.length}${savedViewHasMore ? "+" : ""}`
    : doneFilteredView
      ? `${doneItems.length}${doneHasMore ? "+" : ""}`
      : doneRawTotal;

  const openCol0 = columnQueries[0]?.data;
  const openCol1 = columnQueries[1]?.data;
  const openCol2 = columnQueries[2]?.data;
  useEffect(() => {
    if (smartFilter) return;
    [openCol0, openCol1, openCol2].forEach((data, index) => {
      const typed = data as (ColumnTasks & { offset: number }) | undefined;
      if (!typed) return;
      const colId = OPEN_COLUMNS[index]!.id as OpenColumnId;
      setOpenServerTotals((prev) => ({ ...prev, [colId]: typed.total }));
      setOpenAccum((prev) => ({
        ...prev,
        [colId]: mergeAccumPage(prev[colId], typed.items, typed.offset),
      }));
    });
  }, [smartFilter, openCol0, openCol1, openCol2, accumResetGen]);

  const invalidateBoard = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["tasks", "board"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["views"] });
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
      // Drop accumulated pages so moved cards leave their old columns.
      setOpenOffsets({ ready: 0, in_progress: 0, waiting: 0 });
      setOpenAccum({ ready: [], in_progress: [], waiting: [] });
      setOpenServerTotals({ ready: 0, in_progress: 0, waiting: 0 });
      setSmartOpenOffset(0);
      setSmartOpenAccum([]);
      setDoneRawOffset(0);
      setDoneItems([]);
      setAccumResetGen((g) => g + 1);
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
      setPendingWaiting({ task, note: task.waiting_note ?? "", hints: {} });
      return;
    }
    void runMove(task, value as TaskBoardColumnId);
  };

  const parentTitle = (task: Task) => {
    if (!task.parent_task_id) return null;
    return allTasksById.get(task.parent_task_id)?.title ?? "Subtask";
  };

  const loading = isSavedView
    ? savedViewBoardQuery.isLoading && savedViewOffset === 0
    : (smartFilter
        ? smartOpenQuery.isLoading || scheduledOpenQuery.isLoading
        : columnQueries.some((q) => q.isLoading)) || doneQuery.isLoading;

  const loadMoreDone = () => {
    setDoneRawOffset((prev) => prev + DONE_PAGE_SIZE);
  };

  const loadMoreOpen = (colId: OpenColumnId) => {
    if (isSavedView) {
      setSavedViewOffset((prev) => prev + SAVED_BOARD_PAGE_SIZE);
      return;
    }
    if (smartFilter) {
      setSmartOpenOffset((prev) => prev + OPEN_PAGE_SIZE);
      return;
    }
    setOpenOffsets((prev) => ({
      ...prev,
      [colId]: prev[colId] + OPEN_PAGE_SIZE,
    }));
  };

  const loadMoreSavedDone = () => {
    setSavedViewOffset((prev) => prev + SAVED_BOARD_PAGE_SIZE);
  };

  const resolveDropHints = (
    column: TaskBoardColumnId,
    targetTaskId: string | null,
    edge: "before" | "after" | "append",
    draggedId?: string | null,
  ): DropInsertHint => {
    if (targetTaskId && edge === "before") {
      return { insert_before_id: targetTaskId };
    }
    if (targetTaskId && edge === "after") {
      return { insert_after_id: targetTaskId };
    }
    const colItems = openByColumn[column].filter(
      (t) => !t.is_completed && t.id !== draggedId,
    );
    const last = colItems[colItems.length - 1];
    if (last) {
      return { insert_after_id: last.id };
    }
    return {};
  };

  const applyDrop = (
    task: Task,
    column: TaskBoardColumnId,
    hints: DropInsertHint,
  ) => {
    if (column === "waiting") {
      setPendingWaiting({ task, note: task.waiting_note ?? "", hints });
      return;
    }
    const fromColumn = columnForOpenTask(task);
    const sameColumn = column === fromColumn;
    if (
      sameColumn &&
      !hints.insert_before_id &&
      !hints.insert_after_id
    ) {
      return;
    }
    void runMove(task, column, hints);
  };

  const onColumnDragOver = (e: React.DragEvent, column: TaskBoardColumnId) => {
    e.preventDefault();
    setDragOverColumn(column);
  };

  const onColumnDrop = (e: React.DragEvent, column: TaskBoardColumnId) => {
    e.preventDefault();
    setDragOverColumn(null);
    setDragOverCard(null);
    const raw = e.dataTransfer.getData("application/x-theplan-task-id");
    if (!raw) return;
    const task = allTasksById.get(raw);
    if (!task) return;
    const hints =
      dragOverCard && dragOverCard.taskId !== raw
        ? resolveDropHints(column, dragOverCard.taskId, dragOverCard.edge, raw)
        : resolveDropHints(column, null, "append", raw);
    applyDrop(task, column, hints);
  };

  const onCardDragStart = (e: React.DragEvent, taskId: string) => {
    e.dataTransfer.setData("application/x-theplan-task-id", taskId);
    e.dataTransfer.effectAllowed = "move";
    setDraggingTaskId(taskId);
  };

  const onCardDragEnd = () => {
    setDraggingTaskId(null);
    setDragOverCard(null);
    setDragOverColumn(null);
  };

  const onCardDragOver = (e: React.DragEvent, taskId: string, column: TaskBoardColumnId) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverColumn(column);
    if (draggingTaskId === taskId) return;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const edge: "before" | "after" = e.clientY < rect.top + rect.height / 2 ? "before" : "after";
    setDragOverCard({ taskId, edge });
  };

  const onCardDrop = (e: React.DragEvent, taskId: string, column: TaskBoardColumnId) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverColumn(null);
    setDragOverCard(null);
    const raw = e.dataTransfer.getData("application/x-theplan-task-id");
    if (!raw) return;
    const task = allTasksById.get(raw);
    if (!task) return;
    if (raw === taskId) return;
    const edge =
      dragOverCard?.taskId === taskId
        ? dragOverCard.edge
        : (() => {
            const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
            return e.clientY < rect.top + rect.height / 2 ? "before" : "after";
          })();
    const hints = resolveDropHints(column, taskId, edge, raw);
    applyDrop(task, column, hints);
  };

  const renderCard = (task: Task, column: TaskBoardColumnId) => {
    const dropBefore = dragOverCard?.taskId === task.id && dragOverCard.edge === "before";
    const dropAfter = dragOverCard?.taskId === task.id && dragOverCard.edge === "after";
    const parent = parentTitle(task);
    const projectLabel =
      showProjectContext && task.project_id
        ? projectById.get(task.project_id) ?? "Project"
        : null;
    return (
      <article
        key={task.id}
        className={`task-board-card${selectedTaskId === task.id ? " selected" : ""}${dropBefore ? " drop-before" : ""}${dropAfter ? " drop-after" : ""}`}
        draggable
        onDragStart={(e) => onCardDragStart(e, task.id)}
        onDragEnd={onCardDragEnd}
        onDragOver={(e) => onCardDragOver(e, task.id, column)}
        onDrop={(e) => onCardDrop(e, task.id, column)}
        onClick={() => onSelectTask(task.id)}
        onKeyDown={(e) => {
          // Only activate when the card itself has focus — nested controls
          // (Move to…) need Space/Enter for their own UI.
          if (e.target !== e.currentTarget) return;
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
            onKeyDown={(e) => e.stopPropagation()}
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
    const colId = col.id as OpenColumnId;
    const total = rootsOnly ? items.length : openColumnTotals[colId];
    const hasMore = openColumnHasMore(colId);
    const fetchingMore = isSavedView
      ? savedViewBoardQuery.isFetching && savedViewOffset > 0
      : smartFilter
        ? smartOpenQuery.isFetching && smartOpenOffset > 0
        : columnQueries[OPEN_COLUMNS.findIndex((c) => c.id === col.id)]?.isFetching &&
          openOffsets[colId] > 0;
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
          {items.map((task) => renderCard(task, col.id))}
          {hasMore && (
            <button
              type="button"
              className="btn secondary small task-board-load-more"
              onClick={() => loadMoreOpen(colId)}
              disabled={fetchingMore}
            >
              {fetchingMore ? "Loading…" : "Load more"}
            </button>
          )}
        </div>
      </section>
    );
  };

  const updateWorkFilters = (next: BoardWorkFilters) => {
    setWorkFilters(next);
    writeBoardWorkFilters(next);
  };

  return (
    <div className="task-board-wrap">
      <div className="task-board-toolbar">
        <p className="task-board-wip-summary" role="status">
          WIP (In progress + Waiting): {wipCount} task{wipCount === 1 ? "" : "s"}
        </p>
        <div className="task-board-toolbar-actions">
          {showWorkFilters && (
            <div className="task-board-work-filters">
              <label className="task-board-filter-label">
                <span className="sr-only">Epic</span>
                <select
                  className="task-board-filter-select"
                  value={workFilters.epicId ?? ""}
                  onChange={(e) => {
                    const epicId = e.target.value || null;
                    updateWorkFilters({
                      epicId,
                      projectId:
                        epicId && workFilters.projectId
                          ? (activeProjects.find((p) => p.id === workFilters.projectId)?.epic_id ===
                            epicId
                              ? workFilters.projectId
                              : null)
                          : workFilters.projectId,
                    });
                  }}
                  aria-label="Filter board by epic"
                >
                  <option value="">All epics</option>
                  {(epicsQuery.data?.items ?? []).map((epic) => (
                    <option key={epic.id} value={epic.id}>
                      {epic.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="task-board-filter-label">
                <span className="sr-only">Project</span>
                <select
                  className="task-board-filter-select"
                  value={workFilters.projectId ?? ""}
                  onChange={(e) => {
                    updateWorkFilters({
                      ...workFilters,
                      projectId: e.target.value || null,
                    });
                  }}
                  aria-label="Filter board by project"
                >
                  <option value="">All projects</option>
                  {activeProjects
                    .filter((p) => !workFilters.epicId || p.epic_id === workFilters.epicId)
                    .map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.title}
                      </option>
                    ))}
                </select>
              </label>
            </div>
          )}
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
      </div>

      {loading && <p className="muted">Loading board…</p>}

      <div className="task-board-columns">
        {OPEN_COLUMNS.map(renderOpenColumn)}
        <section className="task-board-column" aria-label="Done column">
          <header className="task-board-column-header">
            <h2 className="task-board-column-title">Done</h2>
            <span className="task-board-column-count">{doneDisplayTotal}</span>
          </header>
          <div
            className={`task-board-column-body${dragOverColumn === DONE_COLUMN ? " drag-over" : ""}`}
            onDragOver={(e) => onColumnDragOver(e, DONE_COLUMN)}
            onDragLeave={() => setDragOverColumn(null)}
            onDrop={(e) => onColumnDrop(e, DONE_COLUMN)}
          >
            {doneColumnItems.length === 0 && !loading && (
              <p className="muted small">No completed tasks loaded</p>
            )}
            {doneColumnItems.map((task) => renderCard(task, DONE_COLUMN))}
            {doneHasMore && (
              <button
                type="button"
                className="btn secondary small task-board-load-more"
                onClick={isSavedView ? loadMoreSavedDone : loadMoreDone}
                disabled={
                  isSavedView
                    ? savedViewBoardQuery.isFetching && savedViewOffset > 0
                    : doneQuery.isFetching
                }
              >
                {(
                  isSavedView
                    ? savedViewBoardQuery.isFetching && savedViewOffset > 0
                    : doneQuery.isFetching
                )
                  ? "Loading…"
                  : "Load more"}
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
                    ...pendingWaiting.hints,
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
