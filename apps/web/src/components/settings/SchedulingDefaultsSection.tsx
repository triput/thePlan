/**
 * Settings — Scheduling defaults form UI.
 * Parent owns user-settings query/mutation + draft; this is presentational.
 */
import type { ScheduleStyle } from "../../api";
import { TimezonePicker } from "../TimezonePicker";
import type { SchedulingDraft } from "./schedulingDraft";

export function SchedulingDefaultsSection({
  draft,
  isLoading,
  isError,
  dirty,
  saving,
  onDraftChange,
  onSave,
}: {
  draft: SchedulingDraft | null;
  isLoading: boolean;
  isError: boolean;
  dirty: boolean;
  saving: boolean;
  onDraftChange: (updater: (prev: SchedulingDraft) => SchedulingDraft) => void;
  onSave: () => void;
}) {
  return (
    <section className="settings-section">
      <h3 className="settings-section-title">Scheduling defaults</h3>
      <p className="settings-help muted small">
        Timezone, work capacity, and planner defaults used when scheduling tasks.
      </p>
      {isLoading && <p className="muted small">Loading scheduling defaults…</p>}
      {isError && (
        <p className="muted small">Couldn't load scheduling defaults — try again later.</p>
      )}
      {draft && !isLoading && (
        <form
          className="scheduling-defaults-form entity-form"
          onSubmit={(e) => {
            e.preventDefault();
            onSave();
          }}
        >
          <label className="field">
            <span>Timezone</span>
            <TimezonePicker
              value={draft.timezone}
              onChange={(timezone) => onDraftChange((prev) => ({ ...prev, timezone }))}
            />
          </label>
          <label className="field">
            <span>Locale</span>
            <input
              type="text"
              value={draft.locale}
              onChange={(e) =>
                onDraftChange((prev) => ({ ...prev, locale: e.target.value }))
              }
              placeholder="en-US"
              spellCheck={false}
              autoComplete="off"
            />
          </label>
          <div className="time-map-time-row">
            <label className="field">
              <span>Workday start</span>
              <input
                type="time"
                value={draft.workday_start_local.slice(0, 5)}
                onChange={(e) =>
                  onDraftChange((prev) => ({
                    ...prev,
                    workday_start_local: e.target.value,
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Workday minutes</span>
              <input
                type="number"
                className="field-number"
                min={1}
                step={1}
                value={draft.workday_minutes}
                onChange={(e) =>
                  onDraftChange((prev) => ({
                    ...prev,
                    workday_minutes: e.target.value,
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Workweek days</span>
              <input
                type="number"
                className="field-number"
                min={1}
                max={7}
                step={1}
                value={draft.workweek_days}
                onChange={(e) =>
                  onDraftChange((prev) => ({
                    ...prev,
                    workweek_days: e.target.value,
                  }))
                }
              />
            </label>
          </div>
          <div className="time-map-time-row">
            <label className="field">
              <span>Buffer between blocks (minutes)</span>
              <input
                type="number"
                className="field-number"
                min={0}
                step={1}
                value={draft.inter_block_buffer_minutes}
                onChange={(e) =>
                  onDraftChange((prev) => ({
                    ...prev,
                    inter_block_buffer_minutes: e.target.value,
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Upcoming horizon (days)</span>
              <input
                type="number"
                className="field-number"
                min={1}
                step={1}
                value={draft.upcoming_horizon_days}
                onChange={(e) =>
                  onDraftChange((prev) => ({
                    ...prev,
                    upcoming_horizon_days: e.target.value,
                  }))
                }
              />
            </label>
          </div>
          <div className="time-map-time-row">
            <label className="field">
              <span>Default task duration (minutes)</span>
              <input
                type="number"
                className="field-number"
                min={1}
                step={1}
                value={draft.default_estimated_duration_minutes}
                onChange={(e) =>
                  onDraftChange((prev) => ({
                    ...prev,
                    default_estimated_duration_minutes: e.target.value,
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Default min block length (minutes)</span>
              <input
                type="number"
                className="field-number"
                min={1}
                step={1}
                value={draft.default_min_block_duration_minutes}
                onChange={(e) =>
                  onDraftChange((prev) => ({
                    ...prev,
                    default_min_block_duration_minutes: e.target.value,
                  }))
                }
              />
            </label>
          </div>
          <label className="field">
            <span>Default schedule style</span>
            <select
              className="field-select"
              value={draft.default_schedule_style}
              onChange={(e) =>
                onDraftChange((prev) => ({
                  ...prev,
                  default_schedule_style: e.target.value as ScheduleStyle,
                }))
              }
            >
              <option value="standalone">Standalone (default)</option>
              <option value="time_block">Time block (opt-in)</option>
              <option value="bundle">Bundle (opt-in)</option>
              <option value="manual">Manual / backlog</option>
            </select>
          </label>
          <label className="field">
            <span>Max minutes per project per day</span>
            <input
              type="number"
              className="field-number"
              min={1}
              step={1}
              placeholder="No cap"
              value={draft.max_auto_schedule_minutes_per_project_per_day}
              onChange={(e) =>
                onDraftChange((prev) => ({
                  ...prev,
                  max_auto_schedule_minutes_per_project_per_day: e.target.value,
                }))
              }
            />
          </label>
          <p className="settings-help muted small">
            Leave empty for no daily cap. Limits auto-scheduled minutes per project on each local
            day during Update Schedule.
          </p>
          <label className="time-map-hard-check">
            <input
              type="checkbox"
              checked={draft.auto_defer_enabled}
              onChange={(e) =>
                onDraftChange((prev) => ({
                  ...prev,
                  auto_defer_enabled: e.target.checked,
                }))
              }
            />
            Auto-defer missed plan windows
          </label>
          <p className="settings-help muted small">
            When on, missed plan windows may slide to a later date. Turn off to keep hard plan
            frames.
          </p>
          <div className="form-actions">
            <button
              type="submit"
              className="btn primary small"
              disabled={saving || !dirty}
            >
              {saving ? "Saving…" : "Save scheduling defaults"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
