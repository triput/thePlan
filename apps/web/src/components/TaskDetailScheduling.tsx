import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  describeApiError,
  fetchHeldMisses,
  fetchSettings,
  fetchTaskScheduleExplanation,
  postLeaveHeld,
  postReleaseHeld,
  postSkipHeld,
  type FocusWindow,
  type HeldDispositionOut,
  type Plan,
  type ScheduleStyle,
  type StaleCategory,
  type Task,
} from "../api";
import { HELD_MISSES_QUERY_KEY, invalidateAfterHeldMutation } from "../heldMissesQuery";
import { formatScheduleReasonFact } from "../scheduleReasonFacts";
import { formatInstantInZone } from "../taskDetailDraft";
import { ConfirmDialog } from "./ConfirmDialog";
import { emitToast } from "./ToastHost";
import { TaskDetailSection, type DetailSectionId } from "./TaskDetailSection";

interface TaskDetailSchedulingProps {
  taskId: string;
  task: Task;
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
  timezone: string;
  datesDirty: boolean;
  onSaveDatesForRelease: () => Promise<boolean>;
  saveDatesPending: boolean;
}

const STALE_LABELS: Record<StaleCategory, string> = {
  duration: "duration changed",
  deadline: "deadline changed",
  map_style: "time map or style changed",
  deps: "dependencies changed",
  pins: "pins changed",
  project_daily_cap: "project daily cap changed",
  timezone_horizon_workweek: "timezone, horizon, or workweek changed",
  lifecycle: "completed, trash, or archive changed",
  busy_external: "busy time changed",
  prerequisite_state: "prerequisite state changed",
  due_at_soft_target: "due date or soft target changed",
  time_map_overrides: "time map overrides changed",
  availability: "availability changed",
  composition: "scheduling rules changed",
  occurrence_bounds: "start window bounds changed",
  occurrence_disposition: "held or skipped occurrence disposition changed",
  priority_ups: "priority or UPS ranking changed",
  scheduling_activation: "scheduling activation changed",
  provenance: "older snapshot",
};

function snapshotInstant(
  snapshot: Record<string, unknown>,
  key: string,
): string | null {
  const value = snapshot[key];
  if (value == null || value === "") return null;
  return String(value);
}

function heldMissSummary(held: HeldDispositionOut): string {
  if (held.miss_reason_code) {
    return formatScheduleReasonFact(
      held.miss_reason_code,
      held.miss_reason_params ?? {},
    );
  }
  return "Held as a missed start window.";
}

export function TaskDetailScheduling({
  taskId,
  task,
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
  timezone,
  datesDirty,
  onSaveDatesForRelease,
  saveDatesPending,
}: TaskDetailSchedulingProps) {
  const isOverbooked = scheduleStatus === "overbooked";
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [skipTarget, setSkipTarget] = useState<HeldDispositionOut | null>(null);

  const explanationQuery = useQuery({
    queryKey: ["schedule-explanation", taskId],
    queryFn: () => fetchTaskScheduleExplanation(taskId),
    enabled: open && Boolean(taskId),
    staleTime: 30_000,
  });

  const heldQuery = useQuery({
    queryKey: HELD_MISSES_QUERY_KEY,
    queryFn: fetchHeldMisses,
    enabled: open && Boolean(taskId),
    staleTime: 15_000,
  });

  const explanationData = explanationQuery.data;
  const explanation = explanationData?.explanation;
  const neverEvaluated = explanationData?.evaluation_state === "never_evaluated";
  const showStale = explanationData?.is_stale ?? false;
  const staleCategories = explanationData?.stale_categories ?? [];

  const heldForTask = (heldQuery.data ?? []).filter(
    (row) => row.task_id === taskId && row.resolution === "unresolved_held",
  );

  const leaveMutation = useMutation({
    mutationFn: async () => {
      const settings = await queryClient.fetchQuery({
        queryKey: ["settings"],
        queryFn: fetchSettings,
      });
      return postLeaveHeld(taskId, {
        expected_revision: settings.scheduling_revision,
      });
    },
    onSuccess: () => {
      setActionError(null);
      emitToast("Acknowledged leave-held — task stays held");
      invalidateAfterHeldMutation(queryClient);
    },
    onError: (err) => {
      const message = describeApiError(err);
      setActionError(message);
      emitToast(`Leave-held failed — ${message}`);
      if (err instanceof ApiError && err.status === 409) {
        void queryClient.invalidateQueries({ queryKey: ["settings"] });
        void queryClient.invalidateQueries({ queryKey: HELD_MISSES_QUERY_KEY });
      }
    },
  });

  const releaseMutation = useMutation({
    mutationFn: async (held: HeldDispositionOut) => {
      if (datesDirty) {
        const saved = await onSaveDatesForRelease();
        if (!saved) {
          throw new Error("Save dates before release failed");
        }
      }
      await queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      await queryClient.invalidateQueries({ queryKey: ["tasks"] });
      await queryClient.invalidateQueries({ queryKey: HELD_MISSES_QUERY_KEY });
      const settings = await queryClient.fetchQuery({
        queryKey: ["settings"],
        queryFn: fetchSettings,
      });
      const heldFresh = await queryClient.fetchQuery({
        queryKey: HELD_MISSES_QUERY_KEY,
        queryFn: fetchHeldMisses,
      });
      const stillHeld = heldFresh.find(
        (row) => row.id === held.id && row.resolution === "unresolved_held",
      );
      if (!stillHeld) {
        throw new Error("Held episode no longer unresolved — refresh and try again");
      }
      // Date-first: bounds already on task via save; release sends named id + rev only.
      return postReleaseHeld(taskId, {
        disposition_id: stillHeld.id,
        expected_revision: settings.scheduling_revision,
      });
    },
    onSuccess: () => {
      setActionError(null);
      emitToast("Released held occurrence");
      invalidateAfterHeldMutation(queryClient);
    },
    onError: (err) => {
      const message =
        err instanceof Error && err.message === "Save dates before release failed"
          ? "Could not save date edits before release."
          : describeApiError(err);
      setActionError(message);
      emitToast(`Release failed — ${message}`);
      // 409: no auto-retry; do not overwrite user edits (form owned by panel).
      if (err instanceof ApiError && err.status === 409) {
        void queryClient.invalidateQueries({ queryKey: ["settings"] });
        void queryClient.invalidateQueries({ queryKey: HELD_MISSES_QUERY_KEY });
      }
    },
  });

  const skipMutation = useMutation({
    mutationFn: async (held: HeldDispositionOut) => {
      const settings = await queryClient.fetchQuery({
        queryKey: ["settings"],
        queryFn: fetchSettings,
      });
      return postSkipHeld(taskId, {
        disposition_id: held.id,
        expected_revision: settings.scheduling_revision,
      });
    },
    onSuccess: () => {
      setSkipTarget(null);
      setActionError(null);
      emitToast("Skipped held occurrence — will not auto-schedule");
      invalidateAfterHeldMutation(queryClient);
    },
    onError: (err) => {
      const message = describeApiError(err);
      setActionError(message);
      emitToast(`Skip failed — ${message}`);
      if (err instanceof ApiError && err.status === 409) {
        void queryClient.invalidateQueries({ queryKey: ["settings"] });
        void queryClient.invalidateQueries({ queryKey: HELD_MISSES_QUERY_KEY });
      }
    },
  });

  const mutationPending =
    leaveMutation.isPending ||
    releaseMutation.isPending ||
    skipMutation.isPending ||
    saveDatesPending;

  return (
    <TaskDetailSection id="scheduling" title="Scheduling" open={open} onToggle={onToggle}>
      {heldQuery.isLoading && (
        <p className="muted small" role="status">
          Loading held…
        </p>
      )}
      {heldQuery.isError && (
        <p className="form-error" role="alert">
          Could not load held misses.{" "}
          <button
            type="button"
            className="btn link small"
            onClick={() => void heldQuery.refetch()}
          >
            Retry
          </button>
        </p>
      )}
      {heldQuery.isSuccess &&
        heldForTask.map((held) => {
          const snap = held.bounds_snapshot ?? {};
          return (
            <div
              key={held.id}
              className="held-miss-banner"
              role="region"
              aria-label="Held miss"
            >
              <p className="held-miss-banner-title">
                <strong>Held miss</strong>
              </p>
              <p className="muted small">{heldMissSummary(held)}</p>
              <div className="held-miss-compare muted small">
                <p>
                  <strong>Original miss</strong> ({timezone}): earliest{" "}
                  {formatInstantInZone(snapshotInstant(snap, "start_no_earlier_at"), timezone)}
                  ; latest{" "}
                  {formatInstantInZone(snapshotInstant(snap, "start_no_later_at"), timezone)}
                  ; deadline{" "}
                  {formatInstantInZone(snapshotInstant(snap, "deadline_at"), timezone)}
                </p>
                <p>
                  <strong>Current dates</strong> ({timezone}): earliest{" "}
                  {formatInstantInZone(task.start_no_earlier_at ?? null, timezone)}; latest{" "}
                  {formatInstantInZone(task.start_no_later_at ?? null, timezone)}; deadline{" "}
                  {formatInstantInZone(task.deadline_at, timezone)}
                </p>
              </div>
              <p className="field-hint muted small">
                Leave held = keep waiting. Release = retry scheduling after you review dates. Skip =
                do not schedule this occurrence; history and blocks stay.
              </p>
              {actionError && (
                <p className="form-error" role="alert">
                  {actionError}
                </p>
              )}
              <div className="form-actions held-miss-actions">
                <button
                  type="button"
                  className="btn secondary small"
                  disabled={mutationPending}
                  onClick={() => leaveMutation.mutate()}
                >
                  {leaveMutation.isPending ? "Leaving…" : "Leave held"}
                </button>
                <button
                  type="button"
                  className="btn secondary small"
                  disabled={mutationPending}
                  onClick={() => setSkipTarget(held)}
                >
                  Skip…
                </button>
                <button
                  type="button"
                  className="btn primary small"
                  disabled={mutationPending}
                  onClick={() => releaseMutation.mutate(held)}
                  title={
                    datesDirty
                      ? "Saves your date edits, then releases this held episode"
                      : "Release this held episode using current task dates"
                  }
                >
                  {releaseMutation.isPending
                    ? "Releasing…"
                    : datesDirty
                      ? "Save dates & release"
                      : "Release"}
                </button>
              </div>
            </div>
          );
        })}

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
                        {formatScheduleReasonFact(fact.code, fact.params)}
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

      <ConfirmDialog
        open={skipTarget !== null}
        title="Skip held occurrence?"
        message="Don’t schedule this occurrence; keep history. The task will no longer block as an unresolved held miss."
        confirmLabel="Skip"
        destructive
        pending={skipMutation.isPending}
        onClose={() => {
          if (!skipMutation.isPending) setSkipTarget(null);
        }}
        onConfirm={() => {
          if (skipTarget) skipMutation.mutate(skipTarget);
        }}
      />
    </TaskDetailSection>
  );
}
