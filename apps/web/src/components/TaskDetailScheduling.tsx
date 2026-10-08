import type { FocusWindow, Plan, ScheduleStyle } from "../api";
import { TaskDetailSection, type DetailSectionId } from "./TaskDetailSection";

interface TaskDetailSchedulingProps {
  open: boolean;
  onToggle: (id: DetailSectionId) => void;
  planId: string;
  plans: Plan[];
  onPlanChange: (value: string) => void;
  duration: string;
  onDurationChange: (value: string) => void;
  preferredTimeWindowId: string;
  onPreferredTimeWindowIdChange: (value: string) => void;
  focusWindows: FocusWindow[];
  inheritTimeMapHint: string | null;
  scheduleStyle: "" | ScheduleStyle;
  onScheduleStyleChange: (value: "" | ScheduleStyle) => void;
  inheritScheduleStyleHint: string | null;
  scheduleStatus: string;
}

export function TaskDetailScheduling({
  open,
  onToggle,
  planId,
  plans,
  onPlanChange,
  duration,
  onDurationChange,
  preferredTimeWindowId,
  onPreferredTimeWindowIdChange,
  focusWindows,
  inheritTimeMapHint,
  scheduleStyle,
  onScheduleStyleChange,
  inheritScheduleStyleHint,
  scheduleStatus,
}: TaskDetailSchedulingProps) {
  const isOverbooked = scheduleStatus === "overbooked";

  return (
    <TaskDetailSection id="scheduling" title="Scheduling" open={open} onToggle={onToggle}>
      {isOverbooked && (
        <p className="scheduling-overbook-note" role="status">
          <strong>Overbooked.</strong> Update Schedule could not fit remaining work before this
          task&apos;s deadline. Free calendar time, shorten duration, or move the deadline, then
          run Update Schedule again. This is not the same as overlap conflicts on the Calendar
          view.
        </p>
      )}
      <label className="field">
        <span>Plan</span>
        <select
          className="field-select"
          value={planId}
          onChange={(e) => onPlanChange(e.target.value)}
        >
          <option value="">None</option>
          {plans.map((plan) => (
            <option key={plan.id} value={plan.id}>
              {plan.name}
            </option>
          ))}
        </select>
        <span className="field-hint muted small">
          Assigning a plan may copy its soft target onto this task
        </span>
      </label>
      <label className="field">
        <span>Duration (minutes)</span>
        <input
          type="number"
          className="field-number"
          min={0}
          step={5}
          value={duration}
          onChange={(e) => onDurationChange(e.target.value)}
          placeholder="30"
        />
      </label>
      <label className="field">
        <span>Time Map</span>
        <select
          className="field-select"
          value={preferredTimeWindowId}
          onChange={(e) => onPreferredTimeWindowIdChange(e.target.value)}
        >
          <option value="">None (inherit)</option>
          {focusWindows.map((window) => (
            <option key={window.id} value={window.id}>
              {window.name}
            </option>
          ))}
        </select>
        {inheritTimeMapHint && (
          <span className="field-hint muted small">{inheritTimeMapHint}</span>
        )}
      </label>
      <label className="field">
        <span>Schedule style</span>
        <select
          className="field-select"
          value={scheduleStyle}
          onChange={(e) => onScheduleStyleChange(e.target.value as "" | ScheduleStyle)}
        >
          <option value="">Inherit</option>
          <option value="standalone">Standalone</option>
          <option value="time_block">Time block</option>
          <option value="bundle">Bundle</option>
          <option value="manual">Manual / backlog</option>
        </select>
        {inheritScheduleStyleHint && (
          <span className="field-hint muted small">{inheritScheduleStyleHint}</span>
        )}
        <span className="field-hint muted small">
          Manual / backlog and bundle tasks are excluded from Update Schedule auto-placement
        </span>
      </label>
    </TaskDetailSection>
  );
}
