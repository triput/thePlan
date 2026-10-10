import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createScheduledBlock,
  clearUnpinnedScheduledBlocks,
  deleteScheduledBlock,
  fetchCalendarConflicts,
  fetchExternalCalendarEvents,
  fetchFocusWindows,
  fetchTimeMapOverrides,
  fetchProjects,
  fetchScheduleRun,
  fetchSchedulePreview,
  fetchScheduledBlocks,
  postSchedulePreview,
  postSchedulePreviewApply,
  fetchSettings,
  fetchTasks,
  postScheduleReplan,
  releaseScheduledBlockRemainder,
  updateScheduledBlock,
  updateTask,
  type Project,
  type SchedulePreviewOut,
  type ScheduleRunOut,
  type ScheduledBlock,
  type StaleCategory,
  type Task,
} from "../api";
import {
  bandWallClockContextForSchedulingDay,
  effectiveTimeMapBandsForDay,
  sortTimeMapBandsForOverlay,
} from "../timeMapOverrides";
import {
  addDays,
  addMinutes,
  CALENDAR_MIN_BLOCK_MINUTES,
  clampToCalendarWindow,
  combineDateAndTime,
  formatHour,
  loadShow24h,
  loadTimeMapOverlayId,
  minutesFromDeltaY,
  resolveHourBounds,
  saveShow24h,
  saveTimeMapOverlayId,
  SHOW_24H_STORAGE_KEY,
  slotFromClick,
  snapMinutes,
  startTimeFromSlotOffset,
  toISO,
  type CalendarMode,
  visibleRange,
  weekDays,
  dayViewTitle,
  weekViewTitle,
  startOfDay,
} from "../calendarUtils";
import { NARROW_QUERY, useMediaQuery } from "../hooks/useMediaQuery";
import { emitToast } from "./ToastHost";
import {
  CalendarBlockMenu,
  fromDatetimeLocalValue,
  toDatetimeLocalValue,
  type BlockFormState,
} from "./CalendarBlockMenu";
import {
  blockDurationMinutes,
  CALENDAR_ROW_HEIGHT_PX,
  CalendarDayColumn,
  type ActiveDrag,
} from "./CalendarDayColumn";
import { CalendarToolbar } from "./CalendarToolbar";
import { SchedulePreviewModal } from "./SchedulePreviewModal";
import {
  blockDurationMinutesForTask,
  readTaskCalendarDrag,
} from "../taskCalendarDrag";

const DRAG_THRESHOLD_PX = 5;
const CALENDAR_HOURS_EVENT = "theplan:calendar-hours";
const REPLAN_POLL_MS = 500;
const REPLAN_TIMEOUT_MS = 60_000;

function dayFromPoint(clientX: number, clientY: number): Date | null {
  const el = document.elementFromPoint(clientX, clientY);
  const host = el?.closest("[data-cal-day]") as HTMLElement | null;
  const raw = host?.dataset.calDay;
  if (!raw) return null;
  return new Date(raw);
}

export function CalendarView() {
  const queryClient = useQueryClient();
  const isNarrow = useMediaQuery(NARROW_QUERY);
  const [mode, setMode] = useState<CalendarMode>("day");
  const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
  const [show24h, setShow24h] = useState(() => loadShow24h());
  const [overlayMapId, setOverlayMapId] = useState(() => loadTimeMapOverlayId());
  const [blockForm, setBlockForm] = useState<BlockFormState | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [drag, setDrag] = useState<ActiveDrag | null>(null);
  const dragRef = useRef<ActiveDrag | null>(null);
  const suppressClickRef = useRef(false);
  const dragListenersRef = useRef<{
    onMove: (e: PointerEvent) => void;
    onUp: (e: PointerEvent) => void;
  } | null>(null);

  useEffect(() => {
    if (isNarrow) setMode("day");
  }, [isNarrow]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === SHOW_24H_STORAGE_KEY) setShow24h(loadShow24h());
    };
    const onHoursEvent = (e: Event) => {
      const detail = (e as CustomEvent<boolean>).detail;
      setShow24h(typeof detail === "boolean" ? detail : loadShow24h());
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener(CALENDAR_HOURS_EVENT, onHoursEvent);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(CALENDAR_HOURS_EVENT, onHoursEvent);
    };
  }, []);

  const hours = useMemo(() => resolveHourBounds(show24h), [show24h]);

  const toggleShow24h = () => {
    const next = !show24h;
    setShow24h(next);
    saveShow24h(next);
    window.dispatchEvent(new CustomEvent(CALENDAR_HOURS_EVENT, { detail: next }));
  };

  const dragEnabled = !isNarrow;
  const range = useMemo(() => visibleRange(anchor, mode), [anchor, mode]);
  const rangeKey = `${toISO(range.start)}-${toISO(range.end)}`;

  const blocksQuery = useQuery({
    queryKey: ["scheduled-blocks", rangeKey],
    queryFn: () =>
      fetchScheduledBlocks({ start: toISO(range.start), end: toISO(range.end) }),
  });

  const busyQuery = useQuery({
    queryKey: ["calendar-events", rangeKey],
    queryFn: () =>
      fetchExternalCalendarEvents({ start: toISO(range.start), end: toISO(range.end) }),
  });

  const conflictsQuery = useQuery({
    queryKey: ["calendar-conflicts", rangeKey],
    queryFn: () =>
      fetchCalendarConflicts({ start: toISO(range.start), end: toISO(range.end) }),
  });

  const dueTasksQuery = useQuery({
    queryKey: ["tasks", "calendar-due", rangeKey],
    queryFn: () =>
      fetchTasks({
        due_from: toISO(range.start),
        due_to: toISO(range.end),
        is_completed: false,
        limit: 500,
      }),
  });

  const incompleteTasksQuery = useQuery({
    queryKey: ["tasks", "incomplete"],
    queryFn: () => fetchTasks({ is_completed: false, limit: 200 }),
  });

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects(),
  });

  const focusWindowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
  });

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });
  const defaultEstimatedDuration =
    settingsQuery.data?.default_estimated_duration_minutes ?? 60;

  const blocks = blocksQuery.data?.items ?? [];
  const blockTaskIds = useMemo(
    () => [...new Set(blocks.map((block) => block.task_id))].sort(),
    [blocks],
  );

  const blockTasksQuery = useQuery({
    queryKey: ["tasks", "calendar-blocks", blockTaskIds.join(",")],
    queryFn: () => fetchTasks({ ids: blockTaskIds, limit: Math.max(blockTaskIds.length, 1) }),
    enabled: blockTaskIds.length > 0,
  });

  const busyEvents = busyQuery.data?.items ?? [];
  const conflicts = conflictsQuery.data?.items ?? [];
  const conflictCount = conflictsQuery.data?.count ?? 0;
  const dueTasks = dueTasksQuery.data?.items ?? [];
  const incompleteTasks = incompleteTasksQuery.data?.items ?? [];

  const { conflictingBlockIds, conflictingBusyEventIds } = useMemo(() => {
    const blockIds = new Set<string>();
    const busyIds = new Set<string>();
    for (const c of conflicts) {
      blockIds.add(c.block_id);
      if (c.other_block_id) blockIds.add(c.other_block_id);
      if (c.external_event_id) busyIds.add(c.external_event_id);
    }
    return { conflictingBlockIds: blockIds, conflictingBusyEventIds: busyIds };
  }, [conflicts]);

  const tasksById = useMemo(() => {
    const map = new Map<string, Task>();
    for (const t of [...dueTasks, ...incompleteTasks, ...(blockTasksQuery.data?.items ?? [])]) {
      map.set(t.id, t);
    }
    return map;
  }, [dueTasks, incompleteTasks, blockTasksQuery.data?.items]);

  const allTasksById = tasksById;

  const projects = useMemo(() => {
    const map = new Map<string, Project>();
    for (const p of projectsQuery.data?.items ?? []) {
      map.set(p.id, p);
    }
    return map;
  }, [projectsQuery.data]);

  const focusWindows = focusWindowsQuery.data ?? [];

  const effectiveOverlayMapId = useMemo(() => {
    if (!overlayMapId) return "";
    return focusWindows.some((w) => w.id === overlayMapId) ? overlayMapId : "";
  }, [focusWindows, overlayMapId]);

  useEffect(() => {
    if (overlayMapId && !effectiveOverlayMapId) {
      setOverlayMapId("");
      saveTimeMapOverlayId("");
    }
  }, [overlayMapId, effectiveOverlayMapId]);

  const overlayFocusWindow = useMemo(() => {
    if (!effectiveOverlayMapId) return undefined;
    return focusWindows.find((w) => w.id === effectiveOverlayMapId);
  }, [effectiveOverlayMapId, focusWindows]);

  const overlayOverridesQuery = useQuery({
    queryKey: ["time-map-overrides", effectiveOverlayMapId],
    queryFn: () => fetchTimeMapOverrides(effectiveOverlayMapId),
    enabled: Boolean(effectiveOverlayMapId) && mode === "week",
  });

  const overlayOverrides = overlayOverridesQuery.data;

  const resolveTimeMapOverlay = useCallback(
    (day: Date) => {
      if (mode !== "week" || !overlayFocusWindow || !settingsQuery.data) {
        return {
          bands: undefined as undefined,
          overrideActive: false,
          bandWallClock: undefined as undefined,
        };
      }
      const { bands, override } = effectiveTimeMapBandsForDay(
        overlayFocusWindow,
        overlayOverrides,
        day,
        settingsQuery.data,
      );
      return {
        bands: sortTimeMapBandsForOverlay(bands),
        overrideActive: override !== null,
        bandWallClock: bandWallClockContextForSchedulingDay(
          day,
          settingsQuery.data,
          override,
        ),
      };
    },
    [mode, overlayFocusWindow, overlayOverrides, settingsQuery.data],
  );

  const setTimeMapOverlay = (mapId: string) => {
    setOverlayMapId(mapId);
    saveTimeMapOverlayId(mapId);
  };

  const invalidateCalendar = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["scheduled-blocks"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-conflicts"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["schedule-explanation"] });
  }, [queryClient]);

  const [replanPolling, setReplanPolling] = useState(false);

  const finishReplanRun = useCallback(
    (run: ScheduleRunOut) => {
      if (run.status === "completed") {
        invalidateCalendar();
        const parts: string[] = [];
        if (run.blocks_created > 0) {
          parts.push(`${run.blocks_created} block${run.blocks_created === 1 ? "" : "s"} created`);
        }
        if (run.overbooked_count > 0) {
          parts.push(`${run.overbooked_count} overbooked`);
        }
        emitToast(
          parts.length > 0 ? `Schedule updated: ${parts.join(", ")}` : "Schedule updated",
        );
        return;
      }
      if (run.status === "failed") {
        emitToast(run.error_message || "Schedule update failed");
      }
    },
    [invalidateCalendar],
  );

  const handleUpdateSchedule = useCallback(async () => {
    if (replanPolling) return;
    setReplanPolling(true);
    try {
      let run = await postScheduleReplan();
      const deadline = Date.now() + REPLAN_TIMEOUT_MS;
      while (run.status === "running" && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, REPLAN_POLL_MS));
        run = await fetchScheduleRun(run.id);
      }
      if (run.status === "running") {
        run = await fetchScheduleRun(run.id);
        if (run.status === "running") {
          emitToast("Schedule update is still running — refresh later to see results");
          return;
        }
      }
      finishReplanRun(run);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        emitToast("A schedule update is already in progress");
        return;
      }
      emitToast(err instanceof Error ? err.message : "Couldn't start schedule update");
    } finally {
      setReplanPolling(false);
    }
  }, [finishReplanRun, replanPolling]);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewPolling, setPreviewPolling] = useState(false);
  const [previewData, setPreviewData] = useState<SchedulePreviewOut | null>(null);
  const [previewApplying, setPreviewApplying] = useState(false);
  const [previewApplyError, setPreviewApplyError] = useState<{
    message: string;
    code?: string;
    staleCategories?: StaleCategory[];
  } | null>(null);

  const pollPreviewUntilSettled = useCallback(async (previewId: string) => {
    let preview = await fetchSchedulePreview(previewId);
    const deadline = Date.now() + REPLAN_TIMEOUT_MS;
    while (preview.status === "running" && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, REPLAN_POLL_MS));
      preview = await fetchSchedulePreview(previewId);
    }
    if (preview.status === "running") {
      preview = await fetchSchedulePreview(previewId);
    }
    return preview;
  }, []);

  const runSchedulePreview = useCallback(async () => {
    setPreviewApplyError(null);
    setPreviewPolling(true);
    setPreviewOpen(true);
    try {
      const started = await postSchedulePreview();
      const settled = await pollPreviewUntilSettled(started.id);
      setPreviewData(settled);
      if (settled.status === "running") {
        emitToast("Preview is still running — refresh from the dialog in a moment");
      }
    } catch (err) {
      emitToast(err instanceof Error ? err.message : "Couldn't start schedule preview");
      setPreviewOpen(false);
      setPreviewData(null);
    } finally {
      setPreviewPolling(false);
    }
  }, [pollPreviewUntilSettled]);

  const refreshSchedulePreview = useCallback(async () => {
    setPreviewApplyError(null);
    setPreviewPolling(true);
    try {
      const started = await postSchedulePreview();
      const settled = await pollPreviewUntilSettled(started.id);
      setPreviewData(settled);
    } catch (err) {
      emitToast(err instanceof Error ? err.message : "Couldn't refresh preview");
    } finally {
      setPreviewPolling(false);
    }
  }, [pollPreviewUntilSettled]);

  const closeSchedulePreview = useCallback(() => {
    if (previewApplying) return;
    setPreviewOpen(false);
    setPreviewApplyError(null);
  }, [previewApplying]);

  const applySchedulePreview = useCallback(async () => {
    if (!previewData || previewApplying) return;
    setPreviewApplying(true);
    setPreviewApplyError(null);
    try {
      const receipt = await postSchedulePreviewApply(previewData.id);
      invalidateCalendar();
      const parts: string[] = [];
      if (receipt.blocks_created > 0) {
        parts.push(`${receipt.blocks_created} block${receipt.blocks_created === 1 ? "" : "s"} created`);
      }
      if (receipt.overbooked_count > 0) {
        parts.push(`${receipt.overbooked_count} overbooked`);
      }
      emitToast(
        parts.length > 0 ? `Preview applied: ${parts.join(", ")}` : "Preview applied",
      );
      setPreviewOpen(false);
      setPreviewData(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setPreviewApplyError({
          message: err.message,
          code: err.code,
          staleCategories: err.body.stale_categories,
        });
        if (err.code === "PREVIEW_STALE" || err.code === "PREVIEW_EXPIRED") {
          try {
            const refreshed = await fetchSchedulePreview(previewData.id);
            setPreviewData(refreshed);
          } catch {
            /* keep prior preview row */
          }
        }
        return;
      }
      emitToast(err instanceof Error ? err.message : "Couldn't apply preview");
    } finally {
      setPreviewApplying(false);
    }
  }, [invalidateCalendar, previewApplying, previewData]);

  const createMutation = useMutation({
    mutationFn: createScheduledBlock,
    onSuccess: invalidateCalendar,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateScheduledBlock>[1] }) =>
      updateScheduledBlock(id, body),
    onSuccess: invalidateCalendar,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteScheduledBlock,
    onSuccess: invalidateCalendar,
  });

  const releaseMutation = useMutation({
    mutationFn: (blockId: string) => releaseScheduledBlockRemainder(blockId),
    onSuccess: invalidateCalendar,
  });

  const clearUnpinnedMutation = useMutation({
    mutationFn: () =>
      clearUnpinnedScheduledBlocks({ start: toISO(range.start), end: toISO(range.end) }),
    onSuccess: (result) => {
      invalidateCalendar();
      emitToast(
        result.deleted_count > 0
          ? `Cleared ${result.deleted_count} unpinned block${result.deleted_count === 1 ? "" : "s"}`
          : "No unpinned blocks to clear in this range",
      );
    },
  });

  const updateDueMutation = useMutation({
    mutationFn: ({ id, due_at }: { id: string; due_at: string }) => updateTask(id, { due_at }),
    onSuccess: invalidateCalendar,
  });

  const detachDragListeners = useCallback(() => {
    const listeners = dragListenersRef.current;
    if (!listeners) return;
    window.removeEventListener("pointermove", listeners.onMove);
    window.removeEventListener("pointerup", listeners.onUp);
    window.removeEventListener("pointercancel", listeners.onUp);
    dragListenersRef.current = null;
  }, []);

  const commitDrag = useCallback(
    async (finalDrag: ActiveDrag) => {
      try {
        if (finalDrag.kind === "due-move") {
          await updateDueMutation.mutateAsync({
            id: finalDrag.taskId,
            due_at: toISO(finalDrag.previewDue),
          });
        } else {
          await updateMutation.mutateAsync({
            id: finalDrag.blockId,
            body: {
              start_time: toISO(finalDrag.previewStart),
              end_time: toISO(finalDrag.previewEnd),
            },
          });
        }
      } catch {
        emitToast("Couldn't update calendar — try again");
        invalidateCalendar();
      }
    },
    [updateMutation, updateDueMutation, invalidateCalendar],
  );

  const beginDrag = useCallback(
    (initial: ActiveDrag) => {
      detachDragListeners();
      dragRef.current = initial;
      setDrag(initial);

      const onMove = (e: PointerEvent) => {
        const current = dragRef.current;
        if (!current) return;
        const deltaY = e.clientY - current.startClientY;
        const moved = current.moved || Math.abs(deltaY) >= DRAG_THRESHOLD_PX;
        if (moved) {
          e.preventDefault();
        }
        const deltaMins = snapMinutes(minutesFromDeltaY(deltaY, CALENDAR_ROW_HEIGHT_PX));

        let next: ActiveDrag = current;
        if (current.kind === "block-move") {
          const duration = blockDurationMinutes(current.originStart, current.originEnd);
          let nextStart = addMinutes(current.originStart, deltaMins);
          const targetDay = dayFromPoint(e.clientX, e.clientY);
          if (targetDay) {
            nextStart = combineDateAndTime(targetDay, nextStart);
          }
          nextStart = clampToCalendarWindow(nextStart, duration, hours);
          next = {
            ...current,
            moved,
            previewStart: nextStart,
            previewEnd: addMinutes(nextStart, duration),
          };
        } else if (current.kind === "block-resize") {
          let nextEnd = addMinutes(current.originEnd, deltaMins);
          const minEnd = addMinutes(current.originStart, CALENDAR_MIN_BLOCK_MINUTES);
          if (nextEnd < minEnd) nextEnd = minEnd;
          const dayEnd = startOfDay(current.originStart);
          dayEnd.setHours(hours.end, 0, 0, 0);
          if (nextEnd > dayEnd) nextEnd = dayEnd;
          next = {
            ...current,
            moved,
            previewStart: current.originStart,
            previewEnd: nextEnd,
          };
        } else {
          let nextDue = addMinutes(current.originDue, deltaMins);
          const targetDay = dayFromPoint(e.clientX, e.clientY);
          if (targetDay) {
            nextDue = combineDateAndTime(targetDay, nextDue);
          }
          nextDue = clampToCalendarWindow(nextDue, 0, hours);
          next = { ...current, moved, previewDue: nextDue };
        }

        dragRef.current = next;
        setDrag(next);
      };

      const onUp = () => {
        const current = dragRef.current;
        detachDragListeners();
        dragRef.current = null;
        setDrag(null);
        if (!current?.moved) return;
        suppressClickRef.current = true;
        window.setTimeout(() => {
          suppressClickRef.current = false;
        }, 0);
        void commitDrag(current);
      };

      dragListenersRef.current = { onMove, onUp };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
    },
    [commitDrag, detachDragListeners, hours],
  );

  useEffect(() => () => detachDragListeners(), [detachDragListeners]);

  const goToday = () => setAnchor(startOfDay(new Date()));

  const goPrev = () => {
    setAnchor((d) => addDays(d, mode === "day" ? -1 : -7));
  };

  const goNext = () => {
    setAnchor((d) => addDays(d, mode === "day" ? 1 : 7));
  };

  const openCreate = (taskId: string, start: Date, end: Date) => {
    setFormMode("create");
    setBlockForm({
      taskId,
      startLocal: toDatetimeLocalValue(start),
      endLocal: toDatetimeLocalValue(end),
      isPinned: false,
    });
  };

  const openEdit = (block: ScheduledBlock) => {
    if (suppressClickRef.current) return;
    setFormMode("edit");
    const memberCount = block.bundle_meta?.member_task_ids?.length;
    setBlockForm({
      blockId: block.id,
      taskId: block.task_id,
      startLocal: toDatetimeLocalValue(new Date(block.start_time)),
      endLocal: toDatetimeLocalValue(new Date(block.end_time)),
      isPinned: block.is_pinned,
      isBundle: block.bundle_meta?.kind === "bundle",
      memberCount,
      bundleInactive: Boolean(block.bundle_inactive),
    });
  };

  const handleSlotClick = (day: Date, offsetY: number) => {
    if (suppressClickRef.current || dragRef.current) return;
    const { start, end } = slotFromClick(day, offsetY, CALENDAR_ROW_HEIGHT_PX, hours);
    openCreate("", start, end);
  };

  const handleDueClick = (task: Task) => {
    if (suppressClickRef.current) return;
    const due = task.due_at ? new Date(task.due_at) : new Date();
    const start = new Date(due);
    if (start.getHours() < hours.start) start.setHours(hours.start, 0, 0, 0);
    const end = new Date(start);
    const mins = task.estimated_duration_minutes || 60;
    end.setMinutes(end.getMinutes() + mins);
    openCreate(task.id, start, end);
  };

  const handleBlockMoveStart = (block: ScheduledBlock, clientY: number) => {
    const originStart = new Date(block.start_time);
    const originEnd = new Date(block.end_time);
    beginDrag({
      kind: "block-move",
      blockId: block.id,
      originStart,
      originEnd,
      previewStart: originStart,
      previewEnd: originEnd,
      startClientY: clientY,
      moved: false,
    });
  };

  const handleBlockResizeStart = (block: ScheduledBlock, clientY: number) => {
    const originStart = new Date(block.start_time);
    const originEnd = new Date(block.end_time);
    beginDrag({
      kind: "block-resize",
      blockId: block.id,
      originStart,
      originEnd,
      previewStart: originStart,
      previewEnd: originEnd,
      startClientY: clientY,
      moved: false,
    });
  };

  const handleDueDragStart = (task: Task, clientY: number) => {
    if (!task.due_at) return;
    const originDue = new Date(task.due_at);
    beginDrag({
      kind: "due-move",
      taskId: task.id,
      originDue,
      previewDue: originDue,
      startClientY: clientY,
      moved: false,
    });
  };

  const handleTaskDrop = useCallback(
    async (day: Date, offsetY: number, dataTransfer: DataTransfer) => {
      if (!dragEnabled) return;
      const payload = readTaskCalendarDrag(dataTransfer);
      if (!payload) return;
      const durationMinutes = blockDurationMinutesForTask(
        payload.estimatedDurationMinutes,
        defaultEstimatedDuration,
      );
      let start = startTimeFromSlotOffset(day, offsetY, CALENDAR_ROW_HEIGHT_PX, hours);
      start = clampToCalendarWindow(start, durationMinutes, hours);
      const end = addMinutes(start, durationMinutes);
      try {
        await createMutation.mutateAsync({
          task_id: payload.taskId,
          start_time: toISO(start),
          end_time: toISO(end),
          is_pinned: false,
        });
        emitToast(`Scheduled "${payload.title}" on the calendar`);
      } catch {
        emitToast("Couldn't schedule task — try again");
        invalidateCalendar();
      }
    },
    [createMutation, defaultEstimatedDuration, dragEnabled, hours, invalidateCalendar],
  );

  const closeForm = () => setBlockForm(null);

  const handleSave = async () => {
    if (!blockForm?.taskId) return;
    const start = fromDatetimeLocalValue(blockForm.startLocal);
    const end = fromDatetimeLocalValue(blockForm.endLocal);
    if (end <= start) return;

    const body = {
      task_id: blockForm.taskId,
      start_time: toISO(start),
      end_time: toISO(end),
      is_pinned: blockForm.isPinned,
    };

    if (formMode === "edit" && blockForm.blockId) {
      await updateMutation.mutateAsync({ id: blockForm.blockId, body });
    } else {
      await createMutation.mutateAsync(body);
    }
    closeForm();
  };

  const handleDelete = async () => {
    if (!blockForm?.blockId) return;
    await deleteMutation.mutateAsync(blockForm.blockId);
    closeForm();
  };

  const handleReleaseRemainder = async () => {
    if (!blockForm?.blockId) return;
    try {
      const result = await releaseMutation.mutateAsync(blockForm.blockId);
      if (result.deleted) {
        emitToast("Block removed — no time left after release");
      } else {
        emitToast("Unused time released");
      }
      closeForm();
    } catch (err) {
      emitToast(err instanceof Error ? err.message : "Couldn't release remainder");
    }
  };

  const handleClearUnpinned = () => {
    const label = mode === "day" ? "today" : "this week";
    if (
      !window.confirm(
        `Remove all unpinned scheduled blocks for ${label}? Pinned blocks stay on the calendar.`,
      )
    ) {
      return;
    }
    void clearUnpinnedMutation.mutateAsync();
  };

  const headerTitle = mode === "day" ? dayViewTitle(anchor) : weekViewTitle(anchor);
  const days = mode === "day" ? [anchor] : weekDays(anchor);

  const formTasks = useMemo(() => {
    const seen = new Set<string>();
    const list: Task[] = [];
    for (const t of incompleteTasks) {
      if (!seen.has(t.id)) {
        seen.add(t.id);
        list.push(t);
      }
    }
    if (blockForm?.taskId && !seen.has(blockForm.taskId)) {
      const t = allTasksById.get(blockForm.taskId);
      if (t) list.unshift(t);
    }
    return list;
  }, [incompleteTasks, blockForm?.taskId, allTasksById]);

  const blockFormTask = blockForm?.taskId ? allTasksById.get(blockForm.taskId) : undefined;

  const blockDrag =
    drag && (drag.kind === "block-move" || drag.kind === "block-resize") ? drag : null;
  const dueDrag = drag && drag.kind === "due-move" ? drag : null;

  return (
    <div className={`calendar-view${drag ? " is-dragging" : ""}`}>
      <CalendarToolbar
        headerTitle={headerTitle}
        conflictCount={conflictCount}
        mode={mode}
        isNarrow={isNarrow}
        show24h={show24h}
        replanPolling={replanPolling}
        previewPolling={previewPolling}
        clearUnpinnedPending={clearUnpinnedMutation.isPending}
        focusWindows={focusWindows}
        effectiveOverlayMapId={effectiveOverlayMapId}
        onPrev={goPrev}
        onNext={goNext}
        onToday={goToday}
        onClearUnpinned={handleClearUnpinned}
        onUpdateSchedule={handleUpdateSchedule}
        onPreviewSchedule={runSchedulePreview}
        onToggleShow24h={toggleShow24h}
        onSetTimeMapOverlay={setTimeMapOverlay}
        onSetMode={setMode}
      />

      <SchedulePreviewModal
        open={previewOpen}
        preview={previewData}
        loading={previewPolling}
        applying={previewApplying}
        applyError={previewApplyError}
        tasksById={allTasksById}
        onClose={closeSchedulePreview}
        onRefresh={refreshSchedulePreview}
        onApply={applySchedulePreview}
      />

      {(blocksQuery.isLoading || dueTasksQuery.isLoading) && (
        <p className="muted small cal-loading">Loading calendar…</p>
      )}

      <div className={`cal-grid-wrap${show24h ? " show-24h" : ""}`}>
        <div className={`cal-grid${mode === "week" ? " week" : " day"}`}>
          <div className="cal-time-gutter">
            {mode === "week" && <div className="cal-gutter-spacer" />}
            {Array.from({ length: hours.hours }, (_, i) => (
              <div key={i} className="cal-time-label" style={{ height: CALENDAR_ROW_HEIGHT_PX }}>
                {formatHour(hours.start + i)}
              </div>
            ))}
          </div>
          <div className={`cal-columns${mode === "week" ? " week" : ""}`}>
            {days.map((day) => {
              const timeMapOverlay = resolveTimeMapOverlay(day);
              return (
              <CalendarDayColumn
                key={day.toISOString()}
                day={day}
                bounds={hours}
                blocks={blocks}
                busyEvents={busyEvents}
                dueTasks={dueTasks}
                tasksById={allTasksById}
                projects={projects}
                dragEnabled={dragEnabled}
                blockPreview={blockDrag}
                duePreview={dueDrag}
                conflictingBlockIds={conflictingBlockIds}
                conflictingBusyEventIds={conflictingBusyEventIds}
                onSlotClick={handleSlotClick}
                onBlockClick={openEdit}
                onDueClick={handleDueClick}
                onBlockMoveStart={handleBlockMoveStart}
                onBlockResizeStart={handleBlockResizeStart}
                onDueDragStart={handleDueDragStart}
                taskDropEnabled={dragEnabled}
                onTaskDrop={handleTaskDrop}
                showDayLabel={mode === "week"}
                timeMapBands={timeMapOverlay.bands}
                timeMapBandWallClock={timeMapOverlay.bandWallClock}
                timeMapOverrideActive={timeMapOverlay.overrideActive}
              />
            );
            })}
          </div>
        </div>
      </div>

      <p className="muted small cal-hint">
        {dragEnabled
          ? "Drag a task from the list onto the calendar, or click a slot to schedule. Drag blocks to move, bottom edge to resize; drag due dots to reschedule."
          : "Tap a time slot to schedule a task. Tap a due dot or block to edit."}
      </p>

      <CalendarBlockMenu
        open={blockForm !== null}
        title={
          formMode === "edit"
            ? blockForm?.isBundle
              ? "Edit calendar bundle"
              : "Edit scheduled block"
            : "Schedule task"
        }
        form={blockForm}
        tasks={formTasks}
        blockTask={blockFormTask}
        onChange={setBlockForm}
        onClose={closeForm}
        onSave={handleSave}
        onDelete={formMode === "edit" ? handleDelete : undefined}
        onReleaseRemainder={formMode === "edit" ? handleReleaseRemainder : undefined}
        saving={createMutation.isPending || updateMutation.isPending}
        deleting={deleteMutation.isPending}
        releasing={releaseMutation.isPending}
      />
    </div>
  );
}
