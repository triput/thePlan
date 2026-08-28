import type { Task } from "../api";
import { TaskDetailSection, type DetailSectionId } from "./TaskDetailSection";

interface TaskDetailRecurrenceProps {
  open: boolean;
  onToggle: (id: DetailSectionId) => void;
  task: Task;
  recurrenceText: string;
  onRecurrenceTextChange: (value: string) => void;
  startsOn: string;
  onStartsOnChange: (value: string) => void;
  endsOn: string;
  onEndsOnChange: (value: string) => void;
  savePending: boolean;
  clearPending: boolean;
  onSave: () => void;
  onClear: () => void;
}

export function TaskDetailRecurrence({
  open,
  onToggle,
  task,
  recurrenceText,
  onRecurrenceTextChange,
  startsOn,
  onStartsOnChange,
  endsOn,
  onEndsOnChange,
  savePending,
  clearPending,
  onSave,
  onClear,
}: TaskDetailRecurrenceProps) {
  return (
    <TaskDetailSection id="recurrence" title="Recurrence" open={open} onToggle={onToggle}>
      <fieldset className="field recurrence-fieldset">
        <legend className="sr-only">Recurrence</legend>
        {task.recurrence?.display && (
          <p className="muted small recurrence-current">{task.recurrence.display}</p>
        )}
        <label className="field">
          <span>Pattern</span>
          <input
            type="text"
            value={recurrenceText}
            onChange={(e) => onRecurrenceTextChange(e.target.value)}
            placeholder="every monday, wednesday"
          />
          <span className="field-hint muted small">
            Use every / every! plus day, week, or weekdays. Optional frame below.
          </span>
        </label>
        <div className="recurrence-frame-row">
          <label className="field">
            <span>From</span>
            <input
              type="date"
              value={startsOn}
              onChange={(e) => onStartsOnChange(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Until</span>
            <input
              type="date"
              value={endsOn}
              onChange={(e) => onEndsOnChange(e.target.value)}
            />
          </label>
        </div>
        <div className="form-actions">
          <button
            type="button"
            className="btn secondary small"
            disabled={!task.recurrence || clearPending}
            onClick={onClear}
          >
            Clear
          </button>
          <button
            type="button"
            className="btn primary small"
            disabled={savePending}
            onClick={onSave}
          >
            {savePending ? "Saving…" : "Save recurrence"}
          </button>
        </div>
      </fieldset>
    </TaskDetailSection>
  );
}
