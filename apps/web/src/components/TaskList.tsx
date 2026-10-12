// ==============================================================================
//  File: apps/web/src/components/TaskList.tsx
//  Description: Task list and board — load-more, saved-view query, presentation hooks (F7-W3).
//  Component: Saved Views
//  Version: 1.0
//  Created: 2026-10-09
//  Last Update: 2026-10-10
// ==============================================================================

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  completeTask,
  createTask,
  fetchLabels,
  fetchPlans,
  fetchProjects,
  fetchScheduledBlocks,
  fetchSections,
  fetchTasks,
  getView,
  patchView,
  queryViewTasks,
  type SavedView,
  reorderSections,
  reorderTasks,
  uncompleteTask,
  type Label,
  type SavedViewInvalidReference,
  type Section,
  type Task,
} from "../api";
import { fetchOpenDescendantIds, useUndoStack } from "../undoStack";
import { PRIORITY_COLORS } from "../colors";
import { useTaskBatchActions } from "../hooks/useTaskBatchActions";
import { buildReorderSwap, canReorderDown, canReorderUp } from "../reorder";
import {
  collectLoadedSubtreeIds,
  hasLoadedDescendants,
  orderTasksForest,
} from "../taskForest";
import {
  endOfLocalDay,
  formatDue,
  formatDuration,
  isToday,
  isUpcoming,
  rangeOverlapsLocalDay,
  startOfLocalDay,
  viewKey,
  viewTitle,
  type ViewSelection,
} from "../view";
import { SavedViewFilterModal } from "./SavedViewFilterModal";
import { CompleteDialog } from "./CompleteDialog";
import { CreateSectionForm } from "./CreateSectionForm";
import { EditSectionForm } from "./EditSectionForm";
import { NARROW_QUERY, useMediaQuery } from "../hooks/useMediaQuery";
import {
  serializeTaskCalendarDrag,
  TASK_CALENDAR_DRAG_MIME,
} from "../taskCalendarDrag";
import { emitToast } from "./ToastHost";
import { ReorderButtons } from "./ReorderButtons";
import { TaskBatchBar } from "./TaskBatchBar";
import { TaskBoard } from "./TaskBoard";
import { mergeAccumPage } from "../boardAccum";
import {
  boardViewSupported,
  mergeSavedViewPresentationMode,
  readTaskPresentation,
  savedViewPresentationMode,
  writeTaskPresentation,
  type TaskPresentation,
} from "../taskPresentation";

const SAVED_LIST_PAGE_SIZE = 200;

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
const OVERBOOKED_ONLY_KEY = "theplan.overbookedOnly";

function isOverbookedStatus(status: string): boolean {
  return status === "overbooked";
}

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
  if (view.type === "saved") {
    return ["views", view.id, "tasks", showCompleted ? "with-completed" : "active"] as const;
  }
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
    workflow_state: "ready",
    board_column: "ready",
    waiting_note: null,
    board_rank: 9999,
    board_revision: 0,
  };
}

export function TaskList({
  view,
  projectTitle,
  selectedTaskId,
  onSelectTask,
}: TaskListProps) {
  const queryClient = useQueryClient();
  const isNarrow = useMediaQuery(NARROW_QUERY);
  const taskCalendarDragEnabled = !isNarrow;
  const { push } = useUndoStack();
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [subtaskParentId, setSubtaskParentId] = useState<string | null>(null);
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [pendingComplete, setPendingComplete] = useState<PendingComplete | null>(null);
  const [editingSection, setEditingSection] = useState<Section | null>(null);
  const [focusedTaskId, setFocusedTaskId] = useState<string | null>(null);
  const [showCompleted, setShowCompleted] = useState(readShowCompleted);
  const [overbookedOnly, setOverbookedOnly] = useState(() => {
    try {
      return localStorage.getItem(OVERBOOKED_ONLY_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const selectAllRef = useRef<HTMLInputElement>(null);
  const rowRefs = useRef<Map<string, HTMLLIElement>>(new Map());
  const vKey = viewKey(view);
  const boardEnabled = boardViewSupported(view);
  const [presentation, setPresentation] = useState<TaskPresentation>(() =>
    readTaskPresentation(vKey),
  );
  const [savedViewEditOpen, setSavedViewEditOpen] = useState(false);
  const [invalidReferences, setInvalidReferences] = useState<SavedViewInvalidReference[]>([]);
  const [savedListOffset, setSavedListOffset] = useState(0);
  const [savedListAccum, setSavedListAccum] = useState<Task[]>([]);
  const [savedListTotal, setSavedListTotal] = useState(0);
  const [savedListResetGen, setSavedListResetGen] = useState(0);

  const savedViewId = view.type === "saved" ? view.id : null;

  const savedViewMetaQuery = useQuery({
    queryKey: ["views", savedViewId],
    queryFn: () => getView(savedViewId!),
    enabled: savedViewId !== null,
  });

  useEffect(() => {
    if (view.type === "saved" && savedViewMetaQuery.data) {
      const fromServer = savedViewPresentationMode(savedViewMetaQuery.data.presentation_json);
      setPresentation(fromServer ?? readTaskPresentation(vKey));
      return;
    }
    setPresentation(readTaskPresentation(vKey));
  }, [vKey, view.type, savedViewMetaQuery.data]);

  useEffect(() => {
    if (view.type !== "saved") return;
    setSavedListOffset(0);
    setSavedListAccum([]);
    setSavedListTotal(0);
    setSavedListResetGen((g) => g + 1);
  }, [view.type === "saved" ? view.id : null]);

  const patchSavedPresentationMutation = useMutation({
    mutationFn: (mode: TaskPresentation) => {
      if (!savedViewId) throw new Error("Missing saved view");
      return patchView(savedViewId, { presentation_json: { mode } });
    },
    onMutate: async (mode) => {
      if (!savedViewId) return {};
      await queryClient.cancelQueries({ queryKey: ["views", savedViewId] });
      const prev = queryClient.getQueryData<SavedView>(["views", savedViewId]);
      if (prev) {
        queryClient.setQueryData<SavedView>(["views", savedViewId], {
          ...prev,
          presentation_json: mergeSavedViewPresentationMode(prev.presentation_json, mode),
        });
      }
      return { prev };
    },
    onError: (_err, _mode, ctx) => {
      if (ctx?.prev && savedViewId) {
        queryClient.setQueryData(["views", savedViewId], ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["views"] });
    },
  });

  const setPresentationPersisted = useCallback(
    (mode: TaskPresentation) => {
      setPresentation(mode);
      writeTaskPresentation(vKey, mode);
      if (view.type === "saved" && savedViewId) {
        patchSavedPresentationMutation.mutate(mode);
      }
    },
    [vKey, view.type, savedViewId, patchSavedPresentationMutation],
  );

  const setShowCompletedPersisted = useCallback((next: boolean) => {
    setShowCompleted(next);
    writeShowCompleted(next);
  }, []);

  const setOverbookedOnlyPersisted = useCallback((next: boolean) => {
    setOverbookedOnly(next);
    try {
      localStorage.setItem(OVERBOOKED_ONLY_KEY, next ? "1" : "0");
    } catch {
      /* ignore */
    }
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

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects({ limit: 200 }),
  });
  const projects = projectsQuery.data?.items ?? [];
  const projectById = useMemo(() => {
    const map = new Map(projects.map((p) => [p.id, p]));
    return map;
  }, [projects]);

  const epicProjects = useMemo(() => {
    if (view.type !== "epic") return [];
    return projects
      .filter((p) => p.epic_id === view.epicId)
      .sort((a, b) => a.sort_order - b.sort_order);
  }, [projects, view]);

  const epicSectionsQuery = useQuery({
    queryKey: ["sections", "epic", view.type === "epic" ? view.epicId : null, epicProjects.map((p) => p.id)],
    enabled: view.type === "epic" && epicProjects.length > 0,
    queryFn: async () => {
      const pages = await Promise.all(epicProjects.map((p) => fetchSections(p.id)));
      return pages.flatMap((page) => page.items);
    },
  });
  const epicSections = epicSectionsQuery.data ?? [];

  const savedCompletion =
    view.type === "saved" && savedViewMetaQuery.data
      ? savedViewMetaQuery.data.predicate_json.dimensions?.completion ?? "open"
      : null;

  const tasksQuery = useQuery({
    queryKey:
      view.type === "saved"
        ? (["views", view.id, "tasks", "list", savedListOffset] as const)
        : tasksCacheKey(view, showCompleted),
    queryFn: async () => {
      if (view.type === "saved") {
        const result = await queryViewTasks(view.id, {
          limit: SAVED_LIST_PAGE_SIZE,
          offset: savedListOffset,
          board_order: false,
        });
        setInvalidReferences(result.invalid_references ?? []);
        return result;
      }
      setInvalidReferences([]);
      const base =
        view.type === "inbox"
          ? { inbox: true as const, limit: 200 }
          : view.type === "work"
            ? { limit: 200 }
            : view.type === "project"
              ? { project_id: view.projectId, limit: 200 }
              : view.type === "epic"
                ? { epic_id: view.epicId, limit: 1000 }
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

  useEffect(() => {
    if (view.type !== "saved" || !tasksQuery.data) return;
    setSavedListTotal(tasksQuery.data.total);
    setSavedListAccum((prev) =>
      mergeAccumPage(prev, tasksQuery.data!.items, savedListOffset),
    );
  }, [view.type, tasksQuery.data, savedListOffset, savedListResetGen]);

  const savedListHasMore =
    view.type === "saved" && savedListAccum.length < savedListTotal;
  const savedListFetchingMore =
    view.type === "saved" && tasksQuery.isFetching && savedListOffset > 0;

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
    enabled: smartRange !== null && view.type !== "saved",
  });

  const sectionsQuery = useQuery({
    queryKey: ["sections", view.type === "project" ? view.projectId : null],
    queryFn: () => fetchSections(view.type === "project" ? view.projectId : ""),
    enabled: view.type === "project",
  });

  const applyClientCompletedFilter = view.type !== "saved" && !showCompleted;

  const overbookedTaskCount = useMemo(() => {
    let items =
      view.type === "saved" ? savedListAccum : (tasksQuery.data?.items ?? []);
    if (applyClientCompletedFilter) {
      items = items.filter((t) => !t.is_completed);
    }
    return items.filter((t) => isOverbookedStatus(t.status)).length;
  }, [tasksQuery.data, savedListAccum, view.type, applyClientCompletedFilter]);

  const tasks = useMemo(() => {
    let items =
      view.type === "saved" ? savedListAccum : (tasksQuery.data?.items ?? []);
    if (applyClientCompletedFilter) {
      items = items.filter((t) => !t.is_completed);
    }
    if (overbookedOnly) {
      items = items.filter((t) => isOverbookedStatus(t.status));
    }
    if (view.type === "today") {
      const scheduledIds = new Set(
        (blocksQuery.data?.items ?? [])
          .filter((b) => rangeOverlapsLocalDay(b.start_time, b.end_time, new Date()))
          .map((b) => b.task_id),
      );
      items = items.filter((t) => isToday(t.due_at) || scheduledIds.has(t.id));
    } else if (view.type === "upcoming") {
      const scheduledIds = new Set((blocksQuery.data?.items ?? []).map((b) => b.task_id));
      items = items.filter((t) => isUpcoming(t.due_at) || scheduledIds.has(t.id));
    }
    // Saved views: keep API/presentation peer order (M1). Hierarchy nesting still applies.
    return orderTasksForest(
      items,
      view.type === "saved" ? { peerOrder: "stable" } : undefined,
    );
  }, [
    tasksQuery.data,
    savedListAccum,
    blocksQuery.data,
    view.type,
    applyClientCompletedFilter,
    overbookedOnly,
  ]);

  const showCompletedToggle =
    view.type !== "saved" || savedCompletion === "any" || savedCompletion === "done";

  const visibleTaskIds = useMemo(() => tasks.map((t) => t.id), [tasks]);

  useEffect(() => {
    setSelectedIds(new Set());
  }, [viewKey(view)]);

  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev;
      const visible = new Set(visibleTaskIds);
      let changed = false;
      const next = new Set<string>();
      for (const id of prev) {
        if (visible.has(id)) next.add(id);
        else changed = true;
      }
      return changed ? next : prev;
    });
  }, [visibleTaskIds]);

  const selectedCount = selectedIds.size;
  const allVisibleSelected =
    visibleTaskIds.length > 0 && visibleTaskIds.every((id) => selectedIds.has(id));
  const someVisibleSelected = visibleTaskIds.some((id) => selectedIds.has(id));

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someVisibleSelected && !allVisibleSelected;
    }
  }, [someVisibleSelected, allVisibleSelected]);

  const toggleSelectTask = (taskId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  const selectLoadedSubtree = (rootId: string) => {
    const ids = collectLoadedSubtreeIds(tasks, rootId);
    if (ids.length === 0) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const id of ids) next.add(id);
      return next;
    });
  };

  const toggleSelectAllVisible = () => {
    setSelectedIds((prev) => {
      if (allVisibleSelected) {
        const next = new Set(prev);
        for (const id of visibleTaskIds) next.delete(id);
        return next;
      }
      const next = new Set(prev);
      for (const id of visibleTaskIds) next.add(id);
      return next;
    });
  };

  const clearSelection = () => setSelectedIds(new Set());

  const invalidateTasks = () => {
    if (view.type === "saved") {
      setSavedListOffset(0);
      setSavedListAccum([]);
      setSavedListResetGen((g) => g + 1);
    }
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["views"] });
  };

  const {
    batchBusy,
    handleBatchScheduleStyle,
    handleBatchApplyLabel,
    handleBatchPriority,
    handleBatchDueDate,
    handleBatchClearDue,
    handleBatchMoveToProject,
    handleBatchDelete,
    handleBlockAsBundle,
  } = useTaskBatchActions({
    selectedIds,
    tasks,
    clearSelection,
    invalidateTasks,
  });

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
      group.sort((a, b) => {
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.id.localeCompare(b.id);
      });
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

  const renderTaskRow = (task: Task) => {
    const siblings = getTaskSiblings(task);
    const isMultiSelected = selectedIds.has(task.id);
    const hasMeta =
      task.priority !== "p4" ||
      Boolean(task.due_at) ||
      Boolean(task.plan_name || task.plan_id) ||
      Boolean(task.soft_target_at) ||
      Boolean(task.deadline_at) ||
      isOverbookedStatus(task.status) ||
      task.estimated_duration_minutes > 0 ||
      task.label_ids.length > 0;
    return (
      <li
        key={task.id}
        ref={(el) => {
          if (el) rowRefs.current.set(task.id, el);
          else rowRefs.current.delete(task.id);
        }}
        className={`task-row${task.is_completed ? " completed" : ""}${selectedTaskId === task.id ? " selected" : ""}${focusedTaskId === task.id ? " focused" : ""}${isMultiSelected ? " multi-selected" : ""}`}
        style={{ paddingLeft: `${12 + task.nesting_level * 20}px` }}
        onClick={(e) => handleTaskRowClick(task, e)}
      >
        <div className="task-row-leading">
          <input
            type="checkbox"
            className="task-select"
            checked={isMultiSelected}
            readOnly
            onClick={(e) => {
              e.stopPropagation();
              if (e.altKey && hasLoadedDescendants(tasks, task.id)) {
                selectLoadedSubtree(task.id);
                return;
              }
              toggleSelectTask(task.id);
            }}
            aria-label={`Select "${task.title}"`}
            title={
              hasLoadedDescendants(tasks, task.id)
                ? "Select for batch (Alt+click includes visible subtasks)"
                : "Select for batch"
            }
          />
          {hasLoadedDescendants(tasks, task.id) && (
            <button
              type="button"
              className="icon-btn tiny select-subtree-btn"
              title="Select this task and all visible subtasks"
              aria-label={`Select "${task.title}" and all visible subtasks`}
              onClick={(e) => {
                e.stopPropagation();
                selectLoadedSubtree(task.id);
              }}
            >
              ⊞
            </button>
          )}
          <input
            type="checkbox"
            className="task-check"
            checked={task.is_completed}
            onChange={() => handleToggleComplete(task)}
            aria-label={`Mark "${task.title}" complete`}
            title={task.is_completed ? "Mark incomplete" : "Mark complete"}
          />
        </div>
        <div className="task-row-body">
          <span className={`task-title${task.is_completed ? " done" : ""}`}>{task.title}</span>
          {hasMeta && (
            <div className="task-row-meta">
              {task.priority !== "p4" && (
                <span className="priority-badge" style={{ color: PRIORITY_COLORS[task.priority] }}>
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
              {isOverbookedStatus(task.status) && (
                <span
                  className="overbooked-badge"
                  title="Scheduler could not fit this task before its deadline"
                >
                  Overbooked
                </span>
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
            </div>
          )}
        </div>
        <div className="task-row-trailing">
          <ReorderButtons
            label={task.title}
            canMoveUp={canReorderUp(siblings, task.id)}
            canMoveDown={canReorderDown(siblings, task.id)}
            onMoveUp={() => handleReorderTask(task, "up")}
            onMoveDown={() => handleReorderTask(task, "down")}
            pending={reorderTasksMutation.isPending}
            className="task-reorder-btns"
          />
          {taskCalendarDragEnabled && !task.is_completed && (
            <button
              type="button"
              className="icon-btn task-calendar-drag-handle"
              draggable
              title="Drag to calendar to schedule"
              aria-label={`Drag "${task.title}" to calendar`}
              onDragStart={(e) => {
                const payload = serializeTaskCalendarDrag({
                  taskId: task.id,
                  title: task.title,
                  estimatedDurationMinutes: task.estimated_duration_minutes,
                });
                e.dataTransfer.setData(TASK_CALENDAR_DRAG_MIME, payload);
                e.dataTransfer.effectAllowed = "copy";
              }}
              onClick={(e) => e.stopPropagation()}
            >
              ⠿
            </button>
          )}
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
        </div>
      </li>
    );
  };

  const heading = viewTitle(view, {
    projectTitle,
    epicTitle: projectTitle,
    labelName: view.type === "label" ? labelsById.get(view.labelId)?.name : undefined,
    savedViewName: savedViewMetaQuery.data?.name,
  });

  const showListChrome = presentation === "list" || !boardEnabled;

  return (
    <div className="task-list-layout">
      <div className={`task-list-pane${presentation === "board" && boardEnabled ? " board-mode" : ""}`}>
        <header className="pane-header">
          <h1>{heading}</h1>
          <div className="pane-header-actions">
            {boardEnabled && (
              <div className="task-view-mode-toggle cal-mode-toggle" role="group" aria-label="Task view">
                <button
                  type="button"
                  className={`btn small${presentation === "list" ? " primary" : " ghost"}`}
                  onClick={() => setPresentationPersisted("list")}
                  aria-pressed={presentation === "list"}
                >
                  List
                </button>
                <button
                  type="button"
                  className={`btn small${presentation === "board" ? " primary" : " ghost"}`}
                  onClick={() => setPresentationPersisted("board")}
                  aria-pressed={presentation === "board"}
                >
                  Board
                </button>
              </div>
            )}
            {showListChrome && view.type === "saved" && (
              <button
                type="button"
                className="btn small secondary"
                onClick={() => setSavedViewEditOpen(true)}
              >
                Edit filters
              </button>
            )}
            {showListChrome && showCompletedToggle && (
            <label className="show-completed-toggle">
              <input
                type="checkbox"
                checked={showCompleted}
                onChange={(e) => setShowCompletedPersisted(e.target.checked)}
              />
              <span>Show completed</span>
            </label>
            )}
            {showListChrome && (overbookedTaskCount > 0 || overbookedOnly) && (
              <label className="overbooked-filter-chip">
                <input
                  type="checkbox"
                  checked={overbookedOnly}
                  onChange={(e) => setOverbookedOnlyPersisted(e.target.checked)}
                />
                <span>
                  Overbooked only
                  {overbookedTaskCount > 0 ? ` (${overbookedTaskCount})` : ""}
                </span>
              </label>
            )}
            {showListChrome && view.type === "project" && (
              <CreateSectionForm projectId={view.projectId} />
            )}
          </div>
        </header>

        {presentation === "board" && boardEnabled ? (
          <TaskBoard
            view={view}
            selectedTaskId={selectedTaskId}
            onSelectTask={onSelectTask}
          />
        ) : (
          <>
        {invalidReferences.length > 0 && view.type === "saved" && (
          <div className="saved-view-repair-banner" role="status">
            <p>
              This view references missing projects, labels, or epics — the list stays empty until
              you repair the filter.
            </p>
            <button
              type="button"
              className="btn secondary small"
              onClick={() => setSavedViewEditOpen(true)}
            >
              Repair filters
            </button>
          </div>
        )}

        {view.type === "project" && sections.length === 0 && (
          <p className="muted small">No sections yet — use Add section above, or tasks sit in one list.</p>
        )}

        {tasksQuery.isLoading && <p className="muted">Loading tasks…</p>}
        {tasksQuery.isError && (
          <p className="form-error">
            Failed to load tasks: {(tasksQuery.error as Error).message}
          </p>
        )}

        {visibleTaskIds.length > 0 && (
          <div className="task-select-toolbar">
            <label className="task-select-all">
              <input
                ref={selectAllRef}
                type="checkbox"
                checked={allVisibleSelected}
                onChange={toggleSelectAllVisible}
                aria-label="Select all visible tasks"
              />
              <span>Select all</span>
            </label>
            {selectedCount > 0 && (
              <span className="muted small">{selectedCount} selected</span>
            )}
          </div>
        )}

        <TaskBatchBar
          selectedCount={selectedCount}
          busy={batchBusy}
          labels={labelsQuery.data?.items ?? []}
          projects={projects}
          projectsLoading={projectsQuery.isLoading}
          onScheduleStyle={handleBatchScheduleStyle}
          onPriority={handleBatchPriority}
          onApplyLabel={handleBatchApplyLabel}
          onDueDate={handleBatchDueDate}
          onClearDue={handleBatchClearDue}
          onMoveToProject={handleBatchMoveToProject}
          onBlockAsBundle={handleBlockAsBundle}
          onDelete={handleBatchDelete}
          onClearSelection={clearSelection}
        />

        {view.type === "epic" ? (
          <div className="epic-task-groups" aria-label={`Tasks in ${heading}`}>
            {tasks.length === 0 && !tasksQuery.isLoading && (
              <p className="empty-state">No tasks here yet.</p>
            )}
            {epicProjects.map((project) => {
              const projectTasks = orderTasksForest(
                tasks.filter((t) => t.project_id === project.id),
              );
              if (projectTasks.length === 0) return null;
              const projectSections = epicSections
                .filter((s) => s.project_id === project.id)
                .sort((a, b) => a.sort_order - b.sort_order);
              return (
                <section key={project.id} className="epic-project-group">
                  <h2 className="epic-project-heading">{project.title}</h2>
                  {projectSections.length > 0 ? (
                    projectSections.map((section) => {
                      const sectionTasks = orderTasksForest(
                        projectTasks.filter((t) => t.section_id === section.id),
                      );
                      if (sectionTasks.length === 0) return null;
                      return (
                        <div key={section.id} className="epic-section-group">
                          <h3 className="epic-section-heading">{section.title}</h3>
                          <ul className="task-list">{sectionTasks.map(renderTaskRow)}</ul>
                        </div>
                      );
                    })
                  ) : (
                    <ul className="task-list">{projectTasks.map(renderTaskRow)}</ul>
                  )}
                </section>
              );
            })}
            {tasks.some((t) => !t.project_id || !projectById.has(t.project_id)) && (
              <section className="epic-project-group">
                <h2 className="epic-project-heading">Other</h2>
                <ul className="task-list">
                  {orderTasksForest(
                    tasks.filter((t) => !t.project_id || !projectById.has(t.project_id)),
                  ).map(renderTaskRow)}
                </ul>
              </section>
            )}
          </div>
        ) : view.type === "project" && sections.length > 0 ? (
          <div className="project-section-groups" aria-label={`Tasks in ${heading}`}>
            {tasks.length === 0 && !tasksQuery.isLoading && (
              <p className="empty-state">No tasks here yet.</p>
            )}
            {sections.map((section) => {
              const sectionTasks = orderTasksForest(
                tasks.filter((t) => t.section_id === section.id),
              );
              return (
                <section key={section.id} className="project-section-group">
                  <div className="project-section-heading-row">
                    <h2 className="project-section-heading">{section.title}</h2>
                    <ReorderButtons
                      label={section.title}
                      canMoveUp={canReorderUp(sections, section.id)}
                      canMoveDown={canReorderDown(sections, section.id)}
                      onMoveUp={() => handleReorderSection(section, "up")}
                      onMoveDown={() => handleReorderSection(section, "down")}
                      pending={reorderSectionsMutation.isPending}
                      className="section-reorder-btns"
                    />
                    <button
                      type="button"
                      className="icon-btn tiny section-edit-btn"
                      title={`Edit ${section.title}`}
                      aria-label={`Edit ${section.title}`}
                      onClick={() => setEditingSection(section)}
                    >
                      ✎
                    </button>
                  </div>
                  {sectionTasks.length === 0 ? (
                    <p className="muted small empty-section">No tasks in this section.</p>
                  ) : (
                    <ul className="task-list">{sectionTasks.map(renderTaskRow)}</ul>
                  )}
                </section>
              );
            })}
            {tasks.some((t) => !t.section_id) && (
              <section className="project-section-group">
                <div className="project-section-heading-row">
                  <h2 className="project-section-heading">No section</h2>
                </div>
                <ul className="task-list">
                  {orderTasksForest(tasks.filter((t) => !t.section_id)).map(renderTaskRow)}
                </ul>
              </section>
            )}
          </div>
        ) : (
          <ul className="task-list" aria-label={`Tasks in ${heading}`}>
            {tasks.length === 0 && !tasksQuery.isLoading && (
              <li className="empty-state">No tasks here yet.</li>
            )}
            {tasks.map(renderTaskRow)}
          </ul>
        )}

        {view.type === "saved" && savedListHasMore && (
          <button
            type="button"
            className="btn secondary small task-board-load-more"
            disabled={savedListFetchingMore}
            onClick={() => setSavedListOffset((prev) => prev + SAVED_LIST_PAGE_SIZE)}
          >
            {savedListFetchingMore ? "Loading…" : "Load more"}
          </button>
        )}

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
            Courses are projects under this epic (expand in the sidebar). Modules are sections —
            open a course to manage them, or browse the grouped list above.
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
          </>
        )}

        {view.type === "saved" && (
          <SavedViewFilterModal
            open={savedViewEditOpen}
            mode="edit"
            viewId={view.id}
            initialName={savedViewMetaQuery.data?.name ?? heading}
            initialPredicate={savedViewMetaQuery.data?.predicate_json}
            initialPresentation={savedViewMetaQuery.data?.presentation_json}
            presentationMode={presentation}
            invalidReferences={invalidReferences}
            onClose={() => setSavedViewEditOpen(false)}
            onSaved={() => {
              queryClient.invalidateQueries({ queryKey: ["views", view.id] });
              invalidateTasks();
            }}
            onDeleted={() => {
              onSelectTask(null);
              window.dispatchEvent(new CustomEvent("theplan:select-inbox"));
            }}
          />
        )}
      </div>
    </div>
  );
}
