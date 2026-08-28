import type { Task } from "../api";
import { Modal } from "./Modal";

export interface BlockFormState {
  taskId: string;
  startLocal: string;
  endLocal: string;
  isPinned: boolean;
  blockId?: string;
  isBundle?: boolean;
  memberCount?: number;
  bundleInactive?: boolean;
}

export function toDatetimeLocalValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromDatetimeLocalValue(value: string): Date {
  return new Date(value);
}

export interface CalendarBlockMenuProps {
  open: boolean;
  title: string;
  form: BlockFormState | null;
  tasks: Task[];
  blockTask?: Task;
  onChange: (next: BlockFormState) => void;
  onClose: () => void;
  onSave: () => void;
  onDelete?: () => void;
  onReleaseRemainder?: () => void;
  saving: boolean;
  deleting: boolean;
  releasing?: boolean;
}

/** Create/edit scheduled-block modal (pin, release remainder, bundle delete). */
export function CalendarBlockMenu({
  open,
  title,
  form,
  tasks,
  blockTask,
  onChange,
  onClose,
  onSave,
  onDelete,
  onReleaseRemainder,
  saving,
  deleting,
  releasing,
}: CalendarBlockMenuProps) {
  if (!form) return null;

  const endDate = fromDatetimeLocalValue(form.endLocal);
  const canReleaseRemainder =
    Boolean(onReleaseRemainder) && endDate.getTime() > Date.now();
  const deleteLabel = form.bundleInactive
    ? "Remove bundle"
    : form.isBundle
      ? "Delete bundle"
      : "Delete";

  return (
    <Modal open={open} title={title} onClose={onClose}>
      <div className="entity-form">
        {form.isBundle && (
          <p className="muted small" role="status">
            Calendar bundle
            {form.memberCount != null ? ` · ${form.memberCount} members` : ""}
            {form.bundleInactive
              ? " — members done or gone; safe to remove (tasks stay)."
              : " — one block on the calendar; members stay individual in lists."}
          </p>
        )}
        {blockTask?.is_completed && !form.isBundle && (
          <p className="muted small" role="status">
            Task completed — release unused time so replan can use the rest of this slot.
          </p>
        )}
        <label className="field">
          <span>{form.isBundle ? "Anchor task" : "Task"}</span>
          <select
            className="field-select"
            value={form.taskId}
            onChange={(e) => onChange({ ...form, taskId: e.target.value })}
            disabled={form.isBundle}
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
          {onReleaseRemainder && canReleaseRemainder && (
            <button
              type="button"
              className="btn secondary"
              onClick={onReleaseRemainder}
              disabled={releasing || saving || deleting}
            >
              {releasing ? "Releasing…" : "Release remainder"}
            </button>
          )}
          {onDelete && (
            <button type="button" className="btn danger" onClick={onDelete} disabled={deleting || saving}>
              {deleting ? "Deleting…" : deleteLabel}
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
