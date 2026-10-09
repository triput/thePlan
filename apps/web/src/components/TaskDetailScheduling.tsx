import { useQuery } from "@tanstack/react-query";
import {
  fetchTaskScheduleExplanation,
  type FocusWindow,
  type Plan,
  type ScheduleStyle,
  type StaleCategory,
} from "../api";
import { TaskDetailSection, type DetailSectionId } from "./TaskDetailSection";

interface TaskDetailSchedulingProps {
  taskId: string;
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

const STALE_LABELS: Record<StaleCategory, string> = {
  duration: "duration changed",
  deadline: "deadline changed",
  map_style: "time map or style changed",
  deps: "dependencies changed",
  provenance: "older snapshot",
};

function formatReasonFact(code: string, params: Record<string, unknown>): string {
  const extras = Object.keys(params).length
    ? ` (${JSON.stringify(params)})`
    : "";
  return `${code}${extras}`;
}

export function TaskDetailScheduling({
  taskId,
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

  const explanationQuery = useQuery({
    queryKey: ["schedule-explanation", taskId],
    queryFn: () => fetchTaskScheduleExplanation(taskId),
    enabled: open && Boolean(taskId),
    staleTime: 30_000,
  });

  const explanationData = explanationQuery.data;
  const explanation = explanationData?.explanation;
  const neverEvaluated = explanationData?.evaluation_state === "never_evaluated";
  const showStale = explanationData?.is_stale ?? false;
  const staleCategories = explanationData?.stale_categories ?? [];

  return (
    <TaskDetailSection id="scheduling" title="Scheduling" open={open} onToggle={onToggle}>
      <div className="schedule-explanation-panel" aria-labelledby="schedule-why-heading">
        <div className="schedule-explanation-header">
          <h4 id="schedule-why-heading" className="schedule-explanation-title">
            Why this schedule?
          </h4>
          {showStale && (
            <span
              className="schedule-stale-badge"
              title={
                staleCategories.length
                  ? `Inputs changed since last run: ${staleCategories.map((c) => STALE_LABELS[c] ?? c).join(", ")}`
                  : "Explanation may be out of date"
              }
            >
              Stale
            </span>
          )}
        </div>
        {explanationQuery.isLoading && (
          <p className="muted small" role="status">
            Loading schedule explanation…
          </p>
        )}
        {explanationQuery.isError && (
          <p className="schedule-explanation-error muted small" role="alert">
            Could not load schedule explanation.
          </p>
        )}
        {explanationQuery.isSuccess && explanationData && (
          <>
            {neverEvaluated ? (
              <p className="schedule-explanation-never muted small" role="status">
                {explanationData.summary_text}
              </p>
            ) : (
              <>
                <p className="schedule-explanation-summary">{explanationData.summary_text}</p>
                {explanation && explanation.reason_facts.length > 0 && (
                  <ul className="schedule-reason-list muted small">
                    {explanation.reason_facts.map((fact, index) => (
                      <li key={`${fact.code}-${index}`}>
                        {formatReasonFact(fact.code, fact.params)}
                      </li>
                    ))}
                  </ul>
                )}
                {explanation?.schedule_run_id && (
                  <p className="schedule-run-ref muted small">
                    From schedule run{" "}
                    <code className="schedule-run-id">{explanation.schedule_run_id}</code>
                  </p>
                )}
              </>
            )}
          </>
        )}
        <p className="field-hint muted small schedule-explanation-hint">
          Read-only — run Update Schedule to refresh placement.
        </p>
      </div>

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
