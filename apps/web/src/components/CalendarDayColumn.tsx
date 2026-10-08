/**
 * Calendar day/week grid column — blocks, due markers, busy overlays.
 * Cut #4 hardening: peeled from CalendarView orchestrator (drag state stays in parent).
 */
import { useState } from "react";
import type { ExternalCalendarEvent, Project, ScheduledBlock, Task, TimeMapBand } from "../api";
import { TASK_CALENDAR_DRAG_MIME } from "../taskCalendarDrag";
import {
  addDays,
  formatShortDate,
  formatWeekday,
  heightPercentForDuration,
  isSameDay,
  isToday,
  startOfDay,
  topPercentForTime,
  type HourBounds,
} from "../calendarUtils";
import { combineDayAndHHMM, dayMatchesBitset, TIME_MAP_TIER_CLASS } from "../focusWindows";
import { DEFAULT_PROJECT_COLOR } from "../colors";

export const CALENDAR_ROW_HEIGHT_PX = 48;

export type ActiveDrag =
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

export function blockDurationMinutes(start: Date, end: Date): number {
  return Math.max(1, (end.getTime() - start.getTime()) / 60_000);
}

function projectColor(projects: Map<string, Project>, projectId: string | null): string {
  if (!projectId) return DEFAULT_PROJECT_COLOR;
  return projects.get(projectId)?.color_hex ?? DEFAULT_PROJECT_COLOR;
}

function TimeMapBandOverlay({
  band,
  day,
  bounds,
}: {
  band: TimeMapBand;
  day: Date;
  bounds: HourBounds;
}) {
  if (!dayMatchesBitset(day, band.days_of_week)) return null;
  const start = combineDayAndHHMM(day, band.start_time);
  const end = combineDayAndHHMM(day, band.end_time);
  if (end <= start) return null;
  const top = topPercentForTime(start, bounds);
  const height = heightPercentForDuration(blockDurationMinutes(start, end), bounds);
  if (top >= 100 || top + height <= 0) return null;

  return (
    <div
      className={`cal-time-map-band ${TIME_MAP_TIER_CLASS[band.tier]}`}
      style={{
        top: `${Math.max(0, top)}%`,
        height: `${Math.min(100 - Math.max(0, top), height)}%`,
      }}
      aria-hidden
    />
  );
}

function BusyBlockItem({
  event,
  bounds,
  hasConflict,
}: {
  event: ExternalCalendarEvent;
  bounds: HourBounds;
  hasConflict?: boolean;
}) {
  const start = new Date(event.start_time);
  const end = new Date(event.end_time);
  const top = topPercentForTime(start, bounds);
  const height = heightPercentForDuration(blockDurationMinutes(start, end), bounds);
  if (top >= 100 || top + height <= 0) return null;

  return (
    <div
      className={`cal-block cal-busy-block${hasConflict ? " conflict" : ""}`}
      style={{
        top: `${Math.max(0, top)}%`,
        height: `${Math.min(100 - Math.max(0, top), height)}%`,
      }}
      title={event.title ? `Busy: ${event.title}` : "Busy (Google Calendar)"}
    >
      <span className="cal-block-title">{event.title ?? "Busy"}</span>
    </div>
  );
}

function DueMarker({
  task,
  color,
  bounds,
  previewDue,
  dragEnabled,
  onClick,
  onDragStart,
}: {
  task: Task;
  color: string;
  bounds: HourBounds;
  previewDue?: Date;
  dragEnabled: boolean;
  onClick: () => void;
  onDragStart: (task: Task, clientY: number) => void;
}) {
  const due = previewDue ?? (task.due_at ? new Date(task.due_at) : null);
  if (!due) return null;
  const top = topPercentForTime(due, bounds);
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
        onDragStart(task, e.clientY);
      }}
    />
  );
}

function ScheduledBlockItem({
  block,
  task,
  color,
  bounds,
  previewStart,
  previewEnd,
  dragEnabled,
  hasConflict,
  isCompleted,
  onClick,
  onMoveStart,
  onResizeStart,
}: {
  block: ScheduledBlock;
  task: Task | undefined;
  color: string;
  bounds: HourBounds;
  previewStart?: Date;
  previewEnd?: Date;
  dragEnabled: boolean;
  hasConflict?: boolean;
  isCompleted?: boolean;
  onClick: () => void;
  onMoveStart: (block: ScheduledBlock, clientY: number) => void;
  onResizeStart: (block: ScheduledBlock, clientY: number) => void;
}) {
  const start = previewStart ?? new Date(block.start_time);
  const end = previewEnd ?? new Date(block.end_time);
  const top = topPercentForTime(start, bounds);
  const height = heightPercentForDuration(blockDurationMinutes(start, end), bounds);
  const dragging = Boolean(previewStart || previewEnd);
  const isBundle = Boolean(block.bundle_meta?.kind === "bundle");
  const inactive = Boolean(block.bundle_inactive) || Boolean(isCompleted);
  const titleBase = task?.title ?? "Scheduled block";
  const displayTitle = isBundle ? `${titleBase} · bundle` : titleBase;

  return (
    <div
      role="button"
      tabIndex={0}
      className={`cal-block${block.is_pinned ? " pinned" : ""}${hasConflict ? " conflict" : ""}${inactive ? " completed" : ""}${isBundle ? " bundle" : ""}${dragging ? " dragging" : ""}`}
      style={{
        top: `${top}%`,
        height: `${height}%`,
        borderLeftColor: color,
        backgroundColor: `color-mix(in srgb, ${color} 22%, var(--panel))`,
      }}
      title={
        hasConflict
          ? `${displayTitle} — schedule conflict`
          : dragEnabled
            ? `${displayTitle} — drag to move, bottom edge to resize`
            : displayTitle
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
        onMoveStart(block, e.clientY);
      }}
    >
      <span className="cal-block-title">{displayTitle}</span>
      {block.is_pinned && <span className="cal-block-pin" aria-label="Pinned">📌</span>}
      {dragEnabled && (
        <span
          className="cal-block-resize"
          aria-hidden
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            e.stopPropagation();
            onResizeStart(block, e.clientY);
          }}
        />
      )}
    </div>
  );
}

export interface CalendarDayColumnProps {
  day: Date;
  bounds: HourBounds;
  blocks: ScheduledBlock[];
  busyEvents: ExternalCalendarEvent[];
  dueTasks: Task[];
  tasksById: Map<string, Task>;
  projects: Map<string, Project>;
  dragEnabled: boolean;
  blockPreview: ActiveDrag | null;
  duePreview: ActiveDrag | null;
  conflictingBlockIds: Set<string>;
  conflictingBusyEventIds: Set<string>;
  timeMapBands?: TimeMapBand[];
  onSlotClick: (day: Date, offsetY: number) => void;
  onBlockClick: (block: ScheduledBlock) => void;
  onDueClick: (task: Task) => void;
  onBlockMoveStart: (block: ScheduledBlock, clientY: number) => void;
  onBlockResizeStart: (block: ScheduledBlock, clientY: number) => void;
  onDueDragStart: (task: Task, clientY: number) => void;
  taskDropEnabled?: boolean;
  onTaskDrop?: (day: Date, offsetY: number, dataTransfer: DataTransfer) => void;
  showDayLabel?: boolean;
}

export function CalendarDayColumn({
  day,
  bounds,
  blocks,
  busyEvents,
  dueTasks,
  tasksById,
  projects,
  dragEnabled,
  blockPreview,
  duePreview,
  conflictingBlockIds,
  conflictingBusyEventIds,
  timeMapBands,
  onSlotClick,
  onBlockClick,
  onDueClick,
  onBlockMoveStart,
  onBlockResizeStart,
  onDueDragStart,
  taskDropEnabled = false,
  onTaskDrop,
  showDayLabel,
}: CalendarDayColumnProps) {
  const [taskDropOver, setTaskDropOver] = useState(false);
  const dayBlocks = blocks.filter((b) => {
    const start =
      blockPreview &&
      (blockPreview.kind === "block-move" || blockPreview.kind === "block-resize") &&
      blockPreview.blockId === b.id
        ? blockPreview.previewStart
        : new Date(b.start_time);
    return isSameDay(start, day);
  });
  const dayBusy = busyEvents.filter((event) => {
    const start = new Date(event.start_time);
    const end = new Date(event.end_time);
    const dayStart = startOfDay(day);
    const dayEnd = addDays(dayStart, 1);
    return start < dayEnd && end > dayStart;
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
        className={`cal-slots${taskDropOver ? " task-drop-over" : ""}`}
        data-cal-day={day.toISOString()}
        onClick={(e) => {
          const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
          onSlotClick(day, e.clientY - rect.top);
        }}
        onDragEnter={(e) => {
          if (!taskDropEnabled || !onTaskDrop) return;
          if (!e.dataTransfer.types.includes(TASK_CALENDAR_DRAG_MIME)) return;
          e.preventDefault();
          setTaskDropOver(true);
        }}
        onDragOver={(e) => {
          if (!taskDropEnabled || !onTaskDrop) return;
          if (!e.dataTransfer.types.includes(TASK_CALENDAR_DRAG_MIME)) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
          setTaskDropOver(true);
        }}
        onDragLeave={(e) => {
          if (!taskDropEnabled) return;
          const next = e.relatedTarget as Node | null;
          if (next && e.currentTarget.contains(next)) return;
          setTaskDropOver(false);
        }}
        onDrop={(e) => {
          setTaskDropOver(false);
          if (!taskDropEnabled || !onTaskDrop) return;
          if (!e.dataTransfer.types.includes(TASK_CALENDAR_DRAG_MIME)) return;
          e.preventDefault();
          e.stopPropagation();
          const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
          onTaskDrop(day, e.clientY - rect.top, e.dataTransfer);
        }}
      >
        {Array.from({ length: bounds.hours }, (_, i) => (
          <div key={i} className="cal-hour-row" style={{ height: CALENDAR_ROW_HEIGHT_PX }} />
        ))}
        <div className="cal-overlay">
          {timeMapBands?.map((band, index) => (
            <TimeMapBandOverlay
              key={`${band.id ?? band.sort_order}-${band.tier}-${index}`}
              band={band}
              day={day}
              bounds={bounds}
            />
          ))}
          {dayBusy.map((event) => (
            <BusyBlockItem
              key={`busy-${event.id}`}
              event={event}
              bounds={bounds}
              hasConflict={conflictingBusyEventIds.has(event.id)}
            />
          ))}
          {dayDue.map((task) => (
            <DueMarker
              key={`due-${task.id}`}
              task={task}
              color={projectColor(projects, task.project_id)}
              bounds={bounds}
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
                bounds={bounds}
                previewStart={preview?.previewStart}
                previewEnd={preview?.previewEnd}
                dragEnabled={dragEnabled}
                hasConflict={conflictingBlockIds.has(block.id)}
                isCompleted={Boolean(block.bundle_inactive) || Boolean(task?.is_completed)}
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
