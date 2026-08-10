import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createScheduledBlock,
  deleteScheduledBlock,
  fetchProjects,
  fetchScheduledBlocks,
  fetchTasks,
  updateScheduledBlock,
  type Project,
  type ScheduledBlock,
  type Task,
} from "../api";
import {
  addDays,
  CALENDAR_HOUR_START,
  CALENDAR_HOURS,
  formatHour,
  formatShortDate,
  formatWeekday,
  heightPercentForDuration,
  isSameDay,
  isToday,
  slotFromClick,
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
import { Modal } from "./Modal";

const ROW_HEIGHT_PX = 48;

interface BlockFormState {
  taskId: string;
  startLocal: string;
  endLocal: string;
  isPinned: boolean;
  blockId?: string;
}

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
  onClick,
}: {
  task: Task;
  color: string;
  onClick: () => void;
}) {
  const due = task.due_at ? new Date(task.due_at) : null;
  if (!due) return null;
  const top = topPercentForTime(due);
  if (top <= 0 || top >= 100) return null;

  return (
    <button
      type="button"
      className="cal-due-marker"
      style={{ top: `${top}%`, borderColor: color, backgroundColor: color }}
      title={`Due: ${task.title}`}
      aria-label={`Due: ${task.title}`}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    />
  );
}

function ScheduledBlockItem({
  block,
  task,
  color,
  onClick,
}: {
  block: ScheduledBlock;
  task: Task | undefined;
  color: string;
  onClick: () => void;
}) {
  const start = new Date(block.start_time);
  const end = new Date(block.end_time);
  const top = topPercentForTime(start);
  const height = heightPercentForDuration(blockDurationMinutes(start, end));

  return (
    <button
      type="button"
      className={`cal-block${block.is_pinned ? " pinned" : ""}`}
      style={{
        top: `${top}%`,
        height: `${height}%`,
        borderLeftColor: color,
        backgroundColor: `color-mix(in srgb, ${color} 22%, var(--panel))`,
      }}
      title={task?.title ?? "Scheduled block"}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <span className="cal-block-title">{task?.title ?? "Block"}</span>
      {block.is_pinned && <span className="cal-block-pin" aria-label="Pinned">📌</span>}
    </button>
  );
}

function DayColumn({
  day,
  blocks,
  dueTasks,
  tasksById,
  projects,
  onSlotClick,
  onBlockClick,
  onDueClick,
  showDayLabel,
}: {
  day: Date;
  blocks: ScheduledBlock[];
  dueTasks: Task[];
  tasksById: Map<string, Task>;
  projects: Map<string, Project>;
  onSlotClick: (day: Date, offsetY: number) => void;
  onBlockClick: (block: ScheduledBlock) => void;
  onDueClick: (task: Task) => void;
  showDayLabel?: boolean;
}) {
  const dayBlocks = blocks.filter((b) => isSameDay(new Date(b.start_time), day));
  const dayDue = dueTasks.filter((t) => t.due_at && isSameDay(new Date(t.due_at), day));

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
              onClick={() => onDueClick(task)}
            />
          ))}
          {dayBlocks.map((block) => {
            const task = tasksById.get(block.task_id);
            return (
              <ScheduledBlockItem
                key={block.id}
                block={block}
                task={task}
                color={projectColor(projects, task?.project_id ?? null)}
                onClick={() => onBlockClick(block)}
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
  const [mode, setMode] = useState<CalendarMode>("day");
  const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
  const [blockForm, setBlockForm] = useState<BlockFormState | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");

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
    const { start, end } = slotFromClick(day, offsetY, ROW_HEIGHT_PX);
    openCreate("", start, end);
  };

  const handleDueClick = (task: Task) => {
    const due = task.due_at ? new Date(task.due_at) : new Date();
    const start = new Date(due);
    if (start.getHours() < CALENDAR_HOUR_START) start.setHours(CALENDAR_HOUR_START, 0, 0, 0);
    const end = new Date(start);
    const mins = task.estimated_duration_minutes || 60;
    end.setMinutes(end.getMinutes() + mins);
    openCreate(task.id, start, end);
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

  return (
    <div className="calendar-view">
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
            className={`btn small${mode === "week" ? " primary" : " ghost"}`}
            onClick={() => setMode("week")}
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
              onSlotClick={handleSlotClick}
              onBlockClick={openEdit}
              onDueClick={handleDueClick}
              showDayLabel={mode === "week"}
            />
          ))}
        </div>
      </div>

      <p className="muted small cal-hint">
        Click a time slot to schedule a task. Click a due dot or block to edit. Due markers use project
        colors.
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
