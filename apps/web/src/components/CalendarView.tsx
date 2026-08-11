import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createScheduledBlock,
  deleteScheduledBlock,
  fetchProjects,
  fetchScheduledBlocks,
  fetchTasks,
  updateScheduledBlock,
  updateTask,
  type Project,
  type ScheduledBlock,
  type Task,
} from "../api";
import {
  addDays,
  addMinutes,
  CALENDAR_HOUR_END,
  CALENDAR_HOUR_START,
  CALENDAR_HOURS,
  CALENDAR_MIN_BLOCK_MINUTES,
  clampToCalendarWindow,
  combineDateAndTime,
  formatHour,
  formatShortDate,
  formatWeekday,
  heightPercentForDuration,
  isSameDay,
  isToday,
  minutesFromDeltaY,
  slotFromClick,
  snapMinutes,
  toISO,
  topPercentForTime,
  type CalendarMode,
  visibleRange,
  weekDays,
  dayViewTitle,
  weekViewTitle,
  startOfDay,
} from "../calendarUtils";
import { DEFAULT_PROJECT_COLOR } from "../colors";
import { NARROW_QUERY, useMediaQuery } from "../hooks/useMediaQuery";
import { emitToast } from "./ToastHost";
import { Modal } from "./Modal";

const ROW_HEIGHT_PX = 48;
const DRAG_THRESHOLD_PX = 5;

interface BlockFormState {
  taskId: string;
  startLocal: string;
  endLocal: string;
  isPinned: boolean;
  blockId?: string;
}

type ActiveDrag =
  | {
      kind: "block-move";
      blockId: string;
      originStart: Date;
      originEnd: Date;
      previewStart: Date;
      previewEnd: Date;
      startClientY: number;
      moved: boolean;
    }
  | {
      kind: "block-resize";
      blockId: string;
      originStart: Date;
      originEnd: Date;
      previewStart: Date;
      previewEnd: Date;
      startClientY: number;
      moved: boolean;
    }
  | {
      kind: "due-move";
      taskId: string;
      originDue: Date;
      previewDue: Date;
      startClientY: number;
      moved: boolean;
    };

function toDatetimeLocalValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocalValue(value: string): Date {
  return new Date(value);
}

function blockDurationMinutes(start: Date, end: Date): number {
  return Math.max(1, (end.getTime() - start.getTime()) / 60_000);
}

function projectColor(projects: Map<string, Project>, projectId: string | null): string {
  if (!projectId) return DEFAULT_PROJECT_COLOR;
  return projects.get(projectId)?.color_hex ?? DEFAULT_PROJECT_COLOR;
}

function dayFromPoint(clientX: number, clientY: number): Date | null {
  const el = document.elementFromPoint(clientX, clientY);
  const host = el?.closest("[data-cal-day]") as HTMLElement | null;
  const raw = host?.dataset.calDay;
  if (!raw) return null;
  return new Date(raw);
}

function BlockFormModal({
  open,
  title,
  form,
  tasks,
  onChange,
  onClose,
  onSave,
  onDelete,
  saving,
  deleting,
}: {
  open: boolean;
  title: string;
  form: BlockFormState | null;
  tasks: Task[];
  onChange: (next: BlockFormState) => void;
  onClose: () => void;
  onSave: () => void;
  onDelete?: () => void;
  saving: boolean;
  deleting: boolean;
}) {
  if (!form) return null;

  return (
    <Modal open={open} title={title} onClose={onClose}>
      <div className="entity-form">
        <label className="field">
          <span>Task</span>
          <select
            className="field-select"
            value={form.taskId}
            onChange={(e) => onChange({ ...form, taskId: e.target.value })}
          >
            <option value="">Select a task…</option>
            {tasks.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Start</span>
          <input
            type="datetime-local"
            className="field-datetime"
            value={form.startLocal}
            onChange={(e) => onChange({ ...form, startLocal: e.target.value })}
          />
        </label>
        <label className="field">
          <span>End</span>
          <input
            type="datetime-local"
            className="field-datetime"
            value={form.endLocal}
            onChange={(e) => onChange({ ...form, endLocal: e.target.value })}
          />
        </label>
        <label className="field cal-pin-field">
          <span>
            <input
              type="checkbox"
              checked={form.isPinned}
              onChange={(e) => onChange({ ...form, isPinned: e.target.checked })}
            />{" "}
            Pinned (won&apos;t move on replan)
          </span>
        </label>
        <div className="form-actions">
          {onDelete && (
            <button type="button" className="btn danger" onClick={onDelete} disabled={deleting || saving}>
              {deleting ? "Deleting…" : "Delete"}
            </button>
          )}
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn primary"
            onClick={onSave}
            disabled={!form.taskId || saving || deleting}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function DueMarker({
  task,
  color,
  previewDue,
  dragEnabled,
  onClick,
  onDragStart,
}: {
  task: Task;
  color: string;
  previewDue?: Date;
  dragEnabled: boolean;
  onClick: () => void;
  onDragStart: (task: Task, clientY: number) => void;
}) {
  const due = previewDue ?? (task.due_at ? new Date(task.due_at) : null);
  if (!due) return null;
  const top = topPercentForTime(due);
  if (top <= 0 || top >= 100) return null;

  return (
    <button
      type="button"
      className={`cal-due-marker${previewDue ? " dragging" : ""}`}
      style={{ top: `${top}%`, borderColor: color, backgroundColor: color }}
      title={dragEnabled ? `Due: ${task.title} (drag to reschedule)` : `Due: ${task.title}`}
      aria-label={`Due: ${task.title}`}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onPointerDown={(e) => {
        if (!dragEnabled || e.button !== 0) return;
        e.stopPropagation();
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        onDragStart(task, e.clientY);
      }}
    />
  );
}

function ScheduledBlockItem({
  block,
  task,
  color,
  previewStart,
  previewEnd,
  dragEnabled,
  onClick,
  onMoveStart,
  onResizeStart,
}: {
  block: ScheduledBlock;
  task: Task | undefined;
  color: string;
  previewStart?: Date;
  previewEnd?: Date;
  dragEnabled: boolean;
  onClick: () => void;
  onMoveStart: (block: ScheduledBlock, clientY: number) => void;
  onResizeStart: (block: ScheduledBlock, clientY: number) => void;
}) {
  const start = previewStart ?? new Date(block.start_time);
  const end = previewEnd ?? new Date(block.end_time);
  const top = topPercentForTime(start);
  const height = heightPercentForDuration(blockDurationMinutes(start, end));
  const dragging = Boolean(previewStart || previewEnd);

  return (
    <div
      role="button"
      tabIndex={0}
      className={`cal-block${block.is_pinned ? " pinned" : ""}${dragging ? " dragging" : ""}`}
      style={{
        top: `${top}%`,
        height: `${height}%`,
        borderLeftColor: color,
        backgroundColor: `color-mix(in srgb, ${color} 22%, var(--panel))`,
      }}
      title={
        dragEnabled
          ? `${task?.title ?? "Scheduled block"} — drag to move, bottom edge to resize`
          : (task?.title ?? "Scheduled block")
      }
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      onPointerDown={(e) => {
        if (!dragEnabled || e.button !== 0) return;
        const target = e.target as HTMLElement;
        if (target.closest(".cal-block-resize")) return;
        e.stopPropagation();
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        onMoveStart(block, e.clientY);
      }}
    >
      <span className="cal-block-title">{task?.title ?? "Block"}</span>
      {block.is_pinned && <span className="cal-block-pin" aria-label="Pinned">📌</span>}
      {dragEnabled && (
        <span
          className="cal-block-resize"
          aria-hidden
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
            onResizeStart(block, e.clientY);
          }}
        />
      )}
    </div>
  );
}

function DayColumn({
  day,
  blocks,
  dueTasks,
  tasksById,
  projects,
  dragEnabled,
  blockPreview,
  duePreview,
  onSlotClick,
  onBlockClick,
  onDueClick,
  onBlockMoveStart,
  onBlockResizeStart,
  onDueDragStart,
  showDayLabel,
}: {
  day: Date;
  blocks: ScheduledBlock[];
  dueTasks: Task[];
  tasksById: Map<string, Task>;
  projects: Map<string, Project>;
  dragEnabled: boolean;
  blockPreview: ActiveDrag | null;
  duePreview: ActiveDrag | null;
  onSlotClick: (day: Date, offsetY: number) => void;
  onBlockClick: (block: ScheduledBlock) => void;
  onDueClick: (task: Task) => void;
  onBlockMoveStart: (block: ScheduledBlock, clientY: number) => void;
  onBlockResizeStart: (block: ScheduledBlock, clientY: number) => void;
  onDueDragStart: (task: Task, clientY: number) => void;
  showDayLabel?: boolean;
}) {
  const dayBlocks = blocks.filter((b) => {
    const start =
      blockPreview &&
      (blockPreview.kind === "block-move" || blockPreview.kind === "block-resize") &&
      blockPreview.blockId === b.id
        ? blockPreview.previewStart
        : new Date(b.start_time);
    return isSameDay(start, day);
  });
  const dayDue = dueTasks.filter((t) => {
    const due =
      duePreview?.kind === "due-move" && duePreview.taskId === t.id
        ? duePreview.previewDue
        : t.due_at
          ? new Date(t.due_at)
          : null;
    return due && isSameDay(due, day);
  });

  return (
    <div className={`cal-day-col${showDayLabel ? " with-label" : ""}`}>
      {showDayLabel && (
        <div className={`cal-col-header${isToday(day) ? " today" : ""}`}>
          <span className="cal-col-weekday">{formatWeekday(day)}</span>
          <span className="cal-col-date">{formatShortDate(day)}</span>
        </div>
      )}
      <div
        className="cal-slots"
        data-cal-day={day.toISOString()}
        onClick={(e) => {
          const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
          onSlotClick(day, e.clientY - rect.top);
        }}
      >
        {Array.from({ length: CALENDAR_HOURS }, (_, i) => (
          <div key={i} className="cal-hour-row" style={{ height: ROW_HEIGHT_PX }} />
        ))}
        <div className="cal-overlay">
          {dayDue.map((task) => (
            <DueMarker
              key={`due-${task.id}`}
              task={task}
              color={projectColor(projects, task.project_id)}
              previewDue={
                duePreview?.kind === "due-move" && duePreview.taskId === task.id
                  ? duePreview.previewDue
                  : undefined
              }
              dragEnabled={dragEnabled}
              onClick={() => onDueClick(task)}
              onDragStart={onDueDragStart}
            />
          ))}
          {dayBlocks.map((block) => {
            const task = tasksById.get(block.task_id);
            const preview =
              blockPreview &&
              (blockPreview.kind === "block-move" || blockPreview.kind === "block-resize") &&
              blockPreview.blockId === block.id
                ? blockPreview
                : null;
            return (
              <ScheduledBlockItem
                key={block.id}
                block={block}
                task={task}
                color={projectColor(projects, task?.project_id ?? null)}
                previewStart={preview?.previewStart}
                previewEnd={preview?.previewEnd}
                dragEnabled={dragEnabled}
                onClick={() => onBlockClick(block)}
                onMoveStart={onBlockMoveStart}
                onResizeStart={onBlockResizeStart}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function CalendarView() {
  const queryClient = useQueryClient();
  const isNarrow = useMediaQuery(NARROW_QUERY);
  const [mode, setMode] = useState<CalendarMode>("day");
  const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
  const [blockForm, setBlockForm] = useState<BlockFormState | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [drag, setDrag] = useState<ActiveDrag | null>(null);
  const dragRef = useRef<ActiveDrag | null>(null);
  const suppressClickRef = useRef(false);

  useEffect(() => {
    if (isNarrow) setMode("day");
  }, [isNarrow]);

  const dragEnabled = !isNarrow;
  const range = useMemo(() => visibleRange(anchor, mode), [anchor, mode]);
  const rangeKey = `${toISO(range.start)}-${toISO(range.end)}`;

  const blocksQuery = useQuery({
    queryKey: ["scheduled-blocks", rangeKey],
    queryFn: () =>
      fetchScheduledBlocks({ start: toISO(range.start), end: toISO(range.end) }),
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

  const blocks = blocksQuery.data?.items ?? [];
  const dueTasks = dueTasksQuery.data?.items ?? [];
  const incompleteTasks = incompleteTasksQuery.data?.items ?? [];

  const tasksById = useMemo(() => {
    const map = new Map<string, Task>();
    for (const t of [...dueTasks, ...incompleteTasks]) {
      map.set(t.id, t);
    }
    return map;
  }, [dueTasks, incompleteTasks]);

  const allTasksById = tasksById;

  const projects = useMemo(() => {
    const map = new Map<string, Project>();
    for (const p of projectsQuery.data?.items ?? []) {
      map.set(p.id, p);
    }
    return map;
  }, [projectsQuery.data]);

  const invalidateCalendar = () => {
    queryClient.invalidateQueries({ queryKey: ["scheduled-blocks"] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

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

  const updateDueMutation = useMutation({
    mutationFn: ({ id, due_at }: { id: string; due_at: string }) => updateTask(id, { due_at }),
    onSuccess: invalidateCalendar,
  });

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
    [updateMutation, updateDueMutation],
  );

  useEffect(() => {
    dragRef.current = drag;
  }, [drag]);

  useEffect(() => {
    if (!drag) return;

    const onMove = (e: PointerEvent) => {
      const current = dragRef.current;
      if (!current) return;
      const deltaY = e.clientY - current.startClientY;
      const moved = current.moved || Math.abs(deltaY) >= DRAG_THRESHOLD_PX;
      const deltaMins = snapMinutes(minutesFromDeltaY(deltaY, ROW_HEIGHT_PX));

      if (current.kind === "block-move") {
        const duration = blockDurationMinutes(current.originStart, current.originEnd);
        let nextStart = addMinutes(current.originStart, deltaMins);
        const targetDay = dayFromPoint(e.clientX, e.clientY);
        if (targetDay) {
          nextStart = combineDateAndTime(targetDay, nextStart);
        }
        nextStart = clampToCalendarWindow(nextStart, duration);
        const nextEnd = addMinutes(nextStart, duration);
        setDrag({ ...current, moved, previewStart: nextStart, previewEnd: nextEnd });
        return;
      }

      if (current.kind === "block-resize") {
        let nextEnd = addMinutes(current.originEnd, deltaMins);
        const minEnd = addMinutes(current.originStart, CALENDAR_MIN_BLOCK_MINUTES);
        if (nextEnd < minEnd) nextEnd = minEnd;
        const dayEnd = startOfDay(current.originStart);
        dayEnd.setHours(CALENDAR_HOUR_END, 0, 0, 0);
        if (nextEnd > dayEnd) nextEnd = dayEnd;
        setDrag({
          ...current,
          moved,
          previewStart: current.originStart,
          previewEnd: nextEnd,
        });
        return;
      }

      if (current.kind === "due-move") {
        let nextDue = addMinutes(current.originDue, deltaMins);
        const targetDay = dayFromPoint(e.clientX, e.clientY);
        if (targetDay) {
          nextDue = combineDateAndTime(targetDay, nextDue);
        }
        nextDue = clampToCalendarWindow(nextDue, 0);
        setDrag({ ...current, moved, previewDue: nextDue });
      }
    };

    const onUp = () => {
      const current = dragRef.current;
      setDrag(null);
      if (!current) return;
      if (!current.moved) return;
      suppressClickRef.current = true;
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
      void commitDrag(current);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [drag !== null, commitDrag]);

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
    setBlockForm({
      blockId: block.id,
      taskId: block.task_id,
      startLocal: toDatetimeLocalValue(new Date(block.start_time)),
      endLocal: toDatetimeLocalValue(new Date(block.end_time)),
      isPinned: block.is_pinned,
    });
  };

  const handleSlotClick = (day: Date, offsetY: number) => {
    if (suppressClickRef.current || drag) return;
    const { start, end } = slotFromClick(day, offsetY, ROW_HEIGHT_PX);
    openCreate("", start, end);
  };

  const handleDueClick = (task: Task) => {
    if (suppressClickRef.current) return;
    const due = task.due_at ? new Date(task.due_at) : new Date();
    const start = new Date(due);
    if (start.getHours() < CALENDAR_HOUR_START) start.setHours(CALENDAR_HOUR_START, 0, 0, 0);
    const end = new Date(start);
    const mins = task.estimated_duration_minutes || 60;
    end.setMinutes(end.getMinutes() + mins);
    openCreate(task.id, start, end);
  };

  const handleBlockMoveStart = (block: ScheduledBlock, clientY: number) => {
    const originStart = new Date(block.start_time);
    const originEnd = new Date(block.end_time);
    setDrag({
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
    setDrag({
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
    setDrag({
      kind: "due-move",
      taskId: task.id,
      originDue,
      previewDue: originDue,
      startClientY: clientY,
      moved: false,
    });
  };

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

  const blockDrag =
    drag && (drag.kind === "block-move" || drag.kind === "block-resize") ? drag : null;
  const dueDrag = drag && drag.kind === "due-move" ? drag : null;

  return (
    <div className={`calendar-view${drag ? " is-dragging" : ""}`}>
      <header className="cal-header">
        <div className="cal-nav">
          <button type="button" className="btn ghost small" onClick={goPrev} aria-label="Previous">
            ‹
          </button>
          <button type="button" className="btn secondary small" onClick={goToday}>
            Today
          </button>
          <button type="button" className="btn ghost small" onClick={goNext} aria-label="Next">
            ›
          </button>
        </div>
        <h1 className="cal-title">{headerTitle}</h1>
        <div className="cal-mode-toggle">
          <button
            type="button"
            className={`btn small${mode === "day" ? " primary" : " ghost"}`}
            onClick={() => setMode("day")}
          >
            Day
          </button>
          <button
            type="button"
            className={`btn small cal-week-btn${mode === "week" ? " primary" : " ghost"}`}
            onClick={() => setMode("week")}
            hidden={isNarrow}
          >
            Week
          </button>
        </div>
      </header>

      {(blocksQuery.isLoading || dueTasksQuery.isLoading) && (
        <p className="muted small cal-loading">Loading calendar…</p>
      )}

      <div className={`cal-grid${mode === "week" ? " week" : " day"}`}>
        <div className="cal-time-gutter">
          {mode === "week" && <div className="cal-gutter-spacer" />}
          {Array.from({ length: CALENDAR_HOURS }, (_, i) => (
            <div key={i} className="cal-time-label" style={{ height: ROW_HEIGHT_PX }}>
              {formatHour(CALENDAR_HOUR_START + i)}
            </div>
          ))}
        </div>
        <div className={`cal-columns${mode === "week" ? " week" : ""}`}>
          {days.map((day) => (
            <DayColumn
              key={day.toISOString()}
              day={day}
              blocks={blocks}
              dueTasks={dueTasks}
              tasksById={allTasksById}
              projects={projects}
              dragEnabled={dragEnabled}
              blockPreview={blockDrag}
              duePreview={dueDrag}
              onSlotClick={handleSlotClick}
              onBlockClick={openEdit}
              onDueClick={handleDueClick}
              onBlockMoveStart={handleBlockMoveStart}
              onBlockResizeStart={handleBlockResizeStart}
              onDueDragStart={handleDueDragStart}
              showDayLabel={mode === "week"}
            />
          ))}
        </div>
      </div>

      <p className="muted small cal-hint">
        {dragEnabled
          ? "Click a slot to schedule. Drag blocks to move, bottom edge to resize; drag due dots to reschedule. Click a block or due for the editor."
          : "Tap a time slot to schedule a task. Tap a due dot or block to edit."}
      </p>

      <BlockFormModal
        open={blockForm !== null}
        title={formMode === "edit" ? "Edit scheduled block" : "Schedule task"}
        form={blockForm}
        tasks={formTasks}
        onChange={setBlockForm}
        onClose={closeForm}
        onSave={handleSave}
        onDelete={formMode === "edit" ? handleDelete : undefined}
        saving={createMutation.isPending || updateMutation.isPending}
        deleting={deleteMutation.isPending}
      />
    </div>
  );
}
