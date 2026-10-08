import { useEffect, useState } from "react";
import type { ScheduleStyle, TaskPriority } from "../api";
import { snapToNext15Minutes } from "../calendarUtils";
import { toDatetimeLocalValue } from "./CalendarBlockMenu";

export interface TaskBatchLabelOption {
  id: string;
  name: string;
}

export interface TaskBatchProjectOption {
  id: string;
  title: string;
  is_archived: boolean;
}

export interface TaskBatchBarProps {
  selectedCount: number;
  busy: boolean;
  labels: ReadonlyArray<TaskBatchLabelOption>;
  projects: ReadonlyArray<TaskBatchProjectOption>;
  projectsLoading?: boolean;
  onScheduleStyle: (style: Extract<ScheduleStyle, "manual" | "standalone">) => void;
  onPriority: (priority: TaskPriority) => void;
  onApplyLabel: (labelId: string) => void;
  onDueDate: (dateValue: string) => void;
  onClearDue: () => void;
  onMoveToProject: (projectId: string | null) => void;
  onBlockAsBundle: (startLocal: string, isPinned: boolean) => void;
  onDelete: () => void;
  onClearSelection: () => void;
}

export function TaskBatchBar({
  selectedCount,
  busy,
  labels,
  projects,
  projectsLoading = false,
  onScheduleStyle,
  onPriority,
  onApplyLabel,
  onDueDate,
  onClearDue,
  onMoveToProject,
  onBlockAsBundle,
  onDelete,
  onClearSelection,
}: TaskBatchBarProps) {
  const [bundleStartLocal, setBundleStartLocal] = useState("");
  const [bundlePinned, setBundlePinned] = useState(false);

  useEffect(() => {
    if (selectedCount <= 0) {
      setBundleStartLocal("");
      setBundlePinned(false);
      return;
    }
    setBundleStartLocal(toDatetimeLocalValue(snapToNext15Minutes()));
  }, [selectedCount]);

  if (selectedCount <= 0) return null;

  return (
    <div className="task-batch-bar" role="toolbar" aria-label="Batch actions">
      <select
        className="task-batch-select"
        defaultValue=""
        disabled={busy}
        aria-label="Set schedule style"
        onChange={(e) => {
          const value = e.target.value as ScheduleStyle | "";
          e.target.value = "";
          if (value === "manual" || value === "standalone") {
            onScheduleStyle(value);
          }
        }}
      >
        <option value="" disabled>
          Schedule style…
        </option>
        <option value="manual">Manual</option>
        <option value="standalone">Standalone</option>
      </select>
      <select
        className="task-batch-select"
        defaultValue=""
        disabled={busy}
        aria-label="Set priority"
        onChange={(e) => {
          const value = e.target.value as TaskPriority | "";
          e.target.value = "";
          if (value === "p1" || value === "p2" || value === "p3" || value === "p4") {
            onPriority(value);
          }
        }}
      >
        <option value="" disabled>
          Priority…
        </option>
        <option value="p1">P1</option>
        <option value="p2">P2</option>
        <option value="p3">P3</option>
        <option value="p4">P4</option>
      </select>
      <select
        className="task-batch-select"
        defaultValue=""
        disabled={busy || labels.length === 0}
        aria-label="Apply label"
        onChange={(e) => {
          const value = e.target.value;
          e.target.value = "";
          if (value) onApplyLabel(value);
        }}
      >
        <option value="" disabled>
          Apply label…
        </option>
        {[...labels]
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((label) => (
            <option key={label.id} value={label.id}>
              {label.name}
            </option>
          ))}
      </select>
      <label className="task-batch-due">
        <span className="sr-only">Set due date</span>
        <input
          type="date"
          className="task-batch-date"
          disabled={busy}
          aria-label="Set due date for selected tasks"
          onChange={(e) => {
            const value = e.target.value;
            e.target.value = "";
            if (value) onDueDate(value);
          }}
        />
      </label>
      <button
        type="button"
        className="btn ghost small"
        disabled={busy}
        onClick={onClearDue}
        title="Clear due date on selected tasks"
      >
        Clear due
      </button>
      <select
        className="task-batch-select"
        defaultValue=""
        disabled={busy || projectsLoading}
        aria-label="Move to project"
        onChange={(e) => {
          const value = e.target.value;
          e.target.value = "";
          if (value === "") return;
          if (value === "__inbox__") {
            onMoveToProject(null);
          } else {
            onMoveToProject(value);
          }
        }}
      >
        <option value="" disabled>
          Move to project…
        </option>
        <option value="__inbox__">Inbox</option>
        {[...projects]
          .filter((p) => !p.is_archived)
          .sort((a, b) => a.title.localeCompare(b.title))
          .map((project) => (
            <option key={project.id} value={project.id}>
              {project.title}
            </option>
          ))}
      </select>
      <label className="task-batch-due">
        <span className="sr-only">Bundle start time</span>
        <input
          type="datetime-local"
          className="task-batch-date task-batch-datetime"
          disabled={busy}
          value={bundleStartLocal}
          aria-label="Bundle start time on calendar"
          onChange={(e) => setBundleStartLocal(e.target.value)}
        />
      </label>
      <label className="task-batch-pin">
        <input
          type="checkbox"
          disabled={busy}
          checked={bundlePinned}
          aria-label="Pin bundle block on calendar"
          onChange={(e) => setBundlePinned(e.target.checked)}
        />
        <span>Pin</span>
      </label>
      <button
        type="button"
        className="btn secondary small"
        disabled={busy || !bundleStartLocal}
        onClick={() => onBlockAsBundle(bundleStartLocal, bundlePinned)}
        title="One calendar block for the selection (or parent subtree)"
      >
        Block as bundle
      </button>
      <button
        type="button"
        className="btn danger small"
        disabled={busy}
        onClick={onDelete}
      >
        Delete
      </button>
      <button
        type="button"
        className="btn ghost small"
        disabled={busy}
        onClick={onClearSelection}
      >
        Clear
      </button>
    </div>
  );
}
