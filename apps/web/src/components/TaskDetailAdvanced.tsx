import type { Reminder, ReminderChannel, SourceRef } from "../api";
import { SourceRefsReadonly } from "./SourceRefsReadonly";
import { TaskDetailSection, type DetailSectionId } from "./TaskDetailSection";

interface TaskDetailAdvancedProps {
  open: boolean;
  onToggle: (id: DetailSectionId) => void;
  upcomingReminders: Reminder[];
  reminderAtLocal: string;
  onReminderAtLocalChange: (value: string) => void;
  reminderChannel: ReminderChannel;
  onReminderChannelChange: (value: ReminderChannel) => void;
  notifPermission: NotificationPermission | "unsupported";
  onRequestBrowserNotifications: () => void;
  createPending: boolean;
  deletePending: boolean;
  onAddReminder: () => void;
  onDeleteReminder: (reminderId: string) => void;
  sourceRefs?: SourceRef[] | null;
}

export function TaskDetailAdvanced({
  open,
  onToggle,
  upcomingReminders,
  reminderAtLocal,
  onReminderAtLocalChange,
  reminderChannel,
  onReminderChannelChange,
  notifPermission,
  onRequestBrowserNotifications,
  createPending,
  deletePending,
  onAddReminder,
  onDeleteReminder,
  sourceRefs,
}: TaskDetailAdvancedProps) {
  return (
    <TaskDetailSection id="advanced" title="Advanced" open={open} onToggle={onToggle}>
      <SourceRefsReadonly sourceRefs={sourceRefs} />
      <fieldset className="field recurrence-fieldset">
        <legend>Reminders</legend>
        {upcomingReminders.length > 0 ? (
          <ul className="reminder-list">
            {upcomingReminders.map((reminder) => (
              <li key={reminder.id} className="reminder-row">
                <span>
                  {new Date(reminder.fire_at).toLocaleString(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                  <span className="muted small">
                    {" "}
                    · {reminder.channel === "browser" ? "browser" : "in-app"}
                  </span>
                </span>
                <button
                  type="button"
                  className="btn secondary small"
                  disabled={deletePending}
                  onClick={() => onDeleteReminder(reminder.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">No upcoming reminders</p>
        )}
        <div className="reminder-add-row">
          <label className="field">
            <span>When</span>
            <input
              type="datetime-local"
              className="field-datetime"
              value={reminderAtLocal}
              onChange={(e) => onReminderAtLocalChange(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Channel</span>
            <select
              className="field-select"
              value={reminderChannel}
              onChange={(e) => onReminderChannelChange(e.target.value as ReminderChannel)}
            >
              <option value="in_app">In-app toast</option>
              <option value="browser">Browser notification</option>
            </select>
          </label>
        </div>
        {notifPermission !== "unsupported" && notifPermission !== "granted" && (
          <button
            type="button"
            className="btn secondary small reminder-notif-btn"
            onClick={onRequestBrowserNotifications}
          >
            Enable browser notifications
          </button>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="btn primary small"
            disabled={!reminderAtLocal || createPending}
            onClick={onAddReminder}
          >
            {createPending ? "Adding…" : "Add reminder"}
          </button>
        </div>
      </fieldset>
    </TaskDetailSection>
  );
}
