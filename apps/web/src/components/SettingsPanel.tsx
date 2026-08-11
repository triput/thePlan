import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createFocusWindow,
  deleteFocusWindow,
  disconnectCalendarAccount,
  fetchCalendarAccounts,
  fetchCalendarSubscriptions,
  fetchFocusWindows,
  fetchGoogleCalendars,
  fetchSettings,
  googleCalendarConnectHref,
  putCalendarSubscriptions,
  syncCalendarAccount,
  updateCalendarAccount,
  updateFocusWindow,
  updateSettings,
  type CalendarAccount,
  type CalendarSubscriptionPutItem,
  type FocusWindow,
  type GoogleCalendarListItem,
  type ScheduleStyle,
  type UserSettings,
  type UserSettingsUpdate,
} from "../api";
import {
  DAY_BITS,
  decodeDays,
  encodeDays,
  formatDaysSummary,
  formatTimeRange,
  WEEKDAY_BITSET,
} from "../focusWindows";
import {
  getThemePreset,
  isValidHex,
  loadOverrides,
  loadTheme,
  normalizeHex,
  OVERRIDE_FIELDS,
  resetOverrides,
  setOverride,
  setTheme,
  THEME_PRESETS,
  type ThemeId,
  type ThemeOverrideKey,
  type ThemeOverrides,
} from "../theme";
import { loadShow24h, saveShow24h } from "../calendarUtils";
import { useAuth } from "../auth";
import { emitToast } from "./ToastHost";
import { HouseholdPanel } from "./HouseholdPanel";
import { Modal } from "./Modal";

const CALENDAR_HOURS_EVENT = "theplan:calendar-hours";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

function effectiveColor(
  themeId: ThemeId,
  key: ThemeOverrideKey,
  overrides: ThemeOverrides,
): string {
  const override = overrides[key];
  if (override) return override;
  const preset = getThemePreset(themeId);
  if (key === "textMuted") return preset.tokens.textMuted;
  return preset.tokens[key];
}

type CalPickerEntry = { checked: boolean; role: "primary" | "informational" };

function buildPickerState(
  calendars: GoogleCalendarListItem[],
  subscriptions: { external_calendar_id: string; role: "primary" | "informational"; is_enabled: boolean }[],
): Record<string, CalPickerEntry> {
  const subById = new Map(subscriptions.map((s) => [s.external_calendar_id, s]));
  const state: Record<string, CalPickerEntry> = {};
  for (const cal of calendars) {
    const sub = subById.get(cal.id);
    if (sub?.is_enabled) {
      state[cal.id] = { checked: true, role: sub.role };
    } else {
      state[cal.id] = { checked: false, role: "informational" };
    }
  }
  const checked = Object.values(state).filter((e) => e.checked);
  if (checked.length === 1) {
    const id = Object.entries(state).find(([, e]) => e.checked)?.[0];
    if (id) state[id] = { checked: true, role: "primary" };
  } else if (checked.length > 0 && !checked.some((e) => e.role === "primary")) {
    const id = Object.entries(state).find(([, e]) => e.checked)?.[0];
    if (id) state[id] = { checked: true, role: "primary" };
  }
  return state;
}

function pickerToPutItems(
  state: Record<string, CalPickerEntry>,
  calendars: GoogleCalendarListItem[],
): CalendarSubscriptionPutItem[] {
  const summaryById = new Map(calendars.map((c) => [c.id, c.summary]));
  const items = Object.entries(state)
    .filter(([, e]) => e.checked)
    .map(([id, e]) => ({
      external_calendar_id: id,
      summary: summaryById.get(id) ?? null,
      role: e.role,
      is_enabled: true,
    }));
  if (items.length === 1) items[0].role = "primary";
  else {
    const primaries = items.filter((i) => i.role === "primary");
    if (primaries.length !== 1 && items.length > 0) {
      items[0].role = "primary";
      for (let i = 1; i < items.length; i++) items[i].role = "informational";
    }
  }
  return items;
}

function CalendarSubscriptionsPicker({
  accountId,
  onSaved,
}: {
  accountId: string;
  onSaved?: () => void;
}) {
  const calendarsQuery = useQuery({
    queryKey: ["google-calendars", accountId],
    queryFn: () => fetchGoogleCalendars(accountId),
  });
  const subsQuery = useQuery({
    queryKey: ["calendar-subscriptions", accountId],
    queryFn: () => fetchCalendarSubscriptions(accountId),
  });

  const calendars = calendarsQuery.data?.items ?? [];
  const subscriptions = subsQuery.data?.items ?? [];

  const [picker, setPicker] = useState<Record<string, CalPickerEntry> | null>(null);
  const [syncAfterSave, setSyncAfterSave] = useState(true);

  useEffect(() => {
    if (calendars.length === 0) return;
    setPicker(buildPickerState(calendars, subscriptions));
  }, [calendarsQuery.dataUpdatedAt, subsQuery.dataUpdatedAt, calendars.length]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!picker) return;
      const items = pickerToPutItems(picker, calendars);
      if (items.length === 0) throw new Error("Select at least one calendar");
      await putCalendarSubscriptions(accountId, items);
      if (syncAfterSave) {
        await syncCalendarAccount(accountId);
      }
    },
    onSuccess: () => {
      emitToast(syncAfterSave ? "Calendars saved and synced" : "Calendars saved");
      onSaved?.();
    },
    onError: () => emitToast("Couldn't save calendar subscriptions"),
  });

  const toggleChecked = useCallback((calId: string, checked: boolean) => {
    setPicker((prev) => {
      if (!prev) return prev;
      const next = { ...prev };
      if (checked) {
        const hasPrimary = Object.entries(next).some(([, e]) => e.checked && e.role === "primary");
        next[calId] = { checked: true, role: hasPrimary ? "informational" : "primary" };
      } else {
        const wasPrimary = next[calId]?.role === "primary";
        next[calId] = { checked: false, role: "informational" };
        if (wasPrimary) {
          const otherChecked = Object.entries(next).find(([id, e]) => id !== calId && e.checked);
          if (otherChecked) next[otherChecked[0]] = { ...otherChecked[1], role: "primary" };
        }
      }
      return next;
    });
  }, []);

  const setPrimary = useCallback((calId: string) => {
    setPicker((prev) => {
      if (!prev || !prev[calId]?.checked) return prev;
      const next = { ...prev };
      for (const id of Object.keys(next)) {
        if (next[id].checked) {
          next[id] = { ...next[id], role: id === calId ? "primary" : "informational" };
        }
      }
      return next;
    });
  }, []);

  if (calendarsQuery.isLoading || subsQuery.isLoading) {
    return <p className="muted small">Loading calendars…</p>;
  }
  if (calendarsQuery.isError) {
    return <p className="muted small">Couldn't load Google calendars — try reconnecting.</p>;
  }
  if (calendars.length === 0) {
    return <p className="muted small">No calendars found on this account.</p>;
  }
  if (!picker) return null;

  const checkedCount = Object.values(picker).filter((e) => e.checked).length;

  return (
    <div className="calendar-sub-picker">
      <p className="settings-help muted small">
        Primary drives busy/availability. Other checked calendars are informational overlays.
        Push goes to primary when mirror is on.
      </p>
      <ul className="calendar-sub-list">
        {calendars.map((cal) => {
          const entry = picker[cal.id] ?? { checked: false, role: "informational" as const };
          const label = cal.summary ?? cal.id;
          return (
            <li key={cal.id} className="calendar-sub-row">
              <label className="calendar-sub-check">
                <input
                  type="checkbox"
                  checked={entry.checked}
                  onChange={(e) => toggleChecked(cal.id, e.target.checked)}
                />
                <span>{label}{cal.primary ? " (Google primary)" : ""}</span>
              </label>
              {entry.checked && checkedCount > 1 && (
                <label className="calendar-sub-primary">
                  <input
                    type="radio"
                    name={`primary-${accountId}`}
                    checked={entry.role === "primary"}
                    onChange={() => setPrimary(cal.id)}
                  />
                  Primary
                </label>
              )}
              {entry.checked && checkedCount === 1 && (
                <span className="calendar-sub-primary-badge muted small">Primary</span>
              )}
            </li>
          );
        })}
      </ul>
      <div className="calendar-sub-actions">
        <label className="calendar-sub-sync-opt">
          <input
            type="checkbox"
            checked={syncAfterSave}
            onChange={(e) => setSyncAfterSave(e.target.checked)}
          />
          Sync after save
        </label>
        <button
          type="button"
          className="btn secondary small"
          disabled={saveMutation.isPending || checkedCount === 0}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? "Saving…" : "Save calendars"}
        </button>
      </div>
    </div>
  );
}

function CalendarAccountRow({
  account,
  onDisconnect,
  onSync,
  disconnectPending,
  syncPending,
  queryClient,
}: {
  account: CalendarAccount;
  onDisconnect: () => void;
  onSync: () => void;
  disconnectPending: boolean;
  syncPending: boolean;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  const [mirror, setMirror] = useState(account.mirror_blocks_to_google);

  useEffect(() => {
    setMirror(account.mirror_blocks_to_google);
  }, [account.mirror_blocks_to_google]);

  const mirrorMutation = useMutation({
    mutationFn: (value: boolean) =>
      updateCalendarAccount(account.id, { mirror_blocks_to_google: value }),
    onMutate: (value) => setMirror(value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-accounts"] });
    },
    onError: () => {
      setMirror(account.mirror_blocks_to_google);
      emitToast("Couldn't update mirror setting");
    },
  });

  const lastSync = account.last_synced_at
    ? new Date(account.last_synced_at).toLocaleString()
    : null;

  return (
    <li className="calendar-account-row">
      <div className="calendar-account-info">
        <div className="calendar-account-email">
          {account.account_email ?? "Google Calendar"}
        </div>
        <div className="muted small">
          {account.provider}
          {lastSync ? ` · last sync ${lastSync}` : ""}
        </div>
        <label className="calendar-mirror-check">
          <input
            type="checkbox"
            checked={mirror}
            disabled={mirrorMutation.isPending}
            onChange={(e) => mirrorMutation.mutate(e.target.checked)}
          />
          Push time blocks to Google
        </label>
        <CalendarSubscriptionsPicker
          accountId={account.id}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ["calendar-subscriptions", account.id] });
            queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
            queryClient.invalidateQueries({ queryKey: ["calendar-accounts"] });
          }}
        />
      </div>
      <div className="calendar-account-actions">
        <button
          type="button"
          className="btn secondary small"
          disabled={syncPending}
          onClick={onSync}
        >
          Sync now
        </button>
        <button
          type="button"
          className="btn ghost small"
          disabled={disconnectPending}
          onClick={onDisconnect}
        >
          Disconnect
        </button>
      </div>
    </li>
  );
}

const EMPTY_FORM = {
  name: "",
  start: "09:00",
  end: "12:00",
  days: decodeDays(WEEKDAY_BITSET),
  isHard: false,
};

type SchedulingDraft = {
  timezone: string;
  locale: string;
  workday_minutes: string;
  workweek_days: string;
  inter_block_buffer_minutes: string;
  upcoming_horizon_days: string;
  default_estimated_duration_minutes: string;
  default_min_block_duration_minutes: string;
  default_schedule_style: ScheduleStyle;
  auto_defer_enabled: boolean;
};

function settingsToDraft(settings: UserSettings): SchedulingDraft {
  return {
    timezone: settings.timezone,
    locale: settings.locale,
    workday_minutes: String(settings.workday_minutes),
    workweek_days: String(settings.workweek_days),
    inter_block_buffer_minutes: String(settings.inter_block_buffer_minutes),
    upcoming_horizon_days: String(settings.upcoming_horizon_days),
    default_estimated_duration_minutes: String(settings.default_estimated_duration_minutes),
    default_min_block_duration_minutes: String(settings.default_min_block_duration_minutes),
    default_schedule_style: settings.default_schedule_style,
    auto_defer_enabled: settings.auto_defer_enabled,
  };
}

function parsePositiveInt(raw: string): number | null {
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

function parseNonNegativeInt(raw: string): number | null {
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value < 0) return null;
  return value;
}

function buildSettingsPatch(saved: UserSettings, draft: SchedulingDraft): UserSettingsUpdate | null {
  const patch: UserSettingsUpdate = {};
  const timezone = draft.timezone.trim();
  const locale = draft.locale.trim();
  if (!timezone) throw new Error("Timezone is required");
  if (!locale) throw new Error("Locale is required");
  if (timezone !== saved.timezone) patch.timezone = timezone;
  if (locale !== saved.locale) patch.locale = locale;

  const workdayMinutes = parsePositiveInt(draft.workday_minutes);
  if (workdayMinutes === null) throw new Error("Workday minutes must be a positive number");
  if (workdayMinutes !== saved.workday_minutes) patch.workday_minutes = workdayMinutes;

  const workweekDays = Number.parseInt(draft.workweek_days, 10);
  if (!Number.isFinite(workweekDays) || workweekDays < 1 || workweekDays > 7) {
    throw new Error("Workweek days must be between 1 and 7");
  }
  if (workweekDays !== saved.workweek_days) patch.workweek_days = workweekDays;

  const bufferMinutes = parseNonNegativeInt(draft.inter_block_buffer_minutes);
  if (bufferMinutes === null) {
    throw new Error("Buffer minutes must be zero or greater");
  }
  if (bufferMinutes !== saved.inter_block_buffer_minutes) {
    patch.inter_block_buffer_minutes = bufferMinutes;
  }

  const horizonDays = parsePositiveInt(draft.upcoming_horizon_days);
  if (horizonDays === null) throw new Error("Upcoming horizon days must be a positive number");
  if (horizonDays !== saved.upcoming_horizon_days) patch.upcoming_horizon_days = horizonDays;

  const defaultDuration = parsePositiveInt(draft.default_estimated_duration_minutes);
  if (defaultDuration === null) {
    throw new Error("Default task duration must be a positive number");
  }
  if (defaultDuration !== saved.default_estimated_duration_minutes) {
    patch.default_estimated_duration_minutes = defaultDuration;
  }

  const minBlockDuration = parsePositiveInt(draft.default_min_block_duration_minutes);
  if (minBlockDuration === null) {
    throw new Error("Default min block length must be a positive number");
  }
  if (minBlockDuration !== saved.default_min_block_duration_minutes) {
    patch.default_min_block_duration_minutes = minBlockDuration;
  }

  if (draft.default_schedule_style !== saved.default_schedule_style) {
    patch.default_schedule_style = draft.default_schedule_style;
  }
  if (draft.auto_defer_enabled !== saved.auto_defer_enabled) {
    patch.auto_defer_enabled = draft.auto_defer_enabled;
  }

  return Object.keys(patch).length > 0 ? patch : null;
}

function isSettingsDirty(saved: UserSettings, draft: SchedulingDraft): boolean {
  try {
    return buildSettingsPatch(saved, draft) !== null;
  } catch {
    return true;
  }
}

function SchedulingDefaultsSection({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["user-settings"],
    queryFn: fetchSettings,
    enabled,
  });

  const [draft, setDraft] = useState<SchedulingDraft | null>(null);

  useEffect(() => {
    if (settingsQuery.data) {
      setDraft(settingsToDraft(settingsQuery.data));
    }
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!settingsQuery.data || !draft) return null;
      const patch = buildSettingsPatch(settingsQuery.data, draft);
      if (!patch) return null;
      return updateSettings(patch);
    },
    onSuccess: (result) => {
      if (result) {
        queryClient.setQueryData(["user-settings"], result);
        setDraft(settingsToDraft(result));
        emitToast("Scheduling defaults saved");
      }
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't save scheduling defaults"),
  });

  const saved = settingsQuery.data;
  const dirty = saved && draft ? isSettingsDirty(saved, draft) : false;

  return (
    <section className="settings-section">
      <h3 className="settings-section-title">Scheduling defaults</h3>
      <p className="settings-help muted small">
        Timezone, work capacity, and planner defaults used when scheduling tasks.
      </p>
      {settingsQuery.isLoading && <p className="muted small">Loading scheduling defaults…</p>}
      {settingsQuery.isError && (
        <p className="muted small">Couldn't load scheduling defaults — try again later.</p>
      )}
      {draft && !settingsQuery.isLoading && (
        <form
          className="scheduling-defaults-form entity-form"
          onSubmit={(e) => {
            e.preventDefault();
            saveMutation.mutate();
          }}
        >
          <label className="field">
            <span>Timezone</span>
            <input
              type="text"
              value={draft.timezone}
              onChange={(e) => setDraft((prev) => prev && { ...prev, timezone: e.target.value })}
              placeholder="America/Los_Angeles"
              spellCheck={false}
              autoComplete="off"
            />
          </label>
          <label className="field">
            <span>Locale</span>
            <input
              type="text"
              value={draft.locale}
              onChange={(e) => setDraft((prev) => prev && { ...prev, locale: e.target.value })}
              placeholder="en-US"
              spellCheck={false}
              autoComplete="off"
            />
          </label>
          <div className="time-map-time-row">
            <label className="field">
              <span>Workday minutes</span>
              <input
                type="number"
                className="field-number"
                min={1}
                step={1}
                value={draft.workday_minutes}
                onChange={(e) =>
                  setDraft((prev) => prev && { ...prev, workday_minutes: e.target.value })
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
                  setDraft((prev) => prev && { ...prev, workweek_days: e.target.value })
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
                  setDraft((prev) => prev && { ...prev, inter_block_buffer_minutes: e.target.value })
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
                  setDraft((prev) => prev && { ...prev, upcoming_horizon_days: e.target.value })
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
                  setDraft((prev) => prev && {
                    ...prev,
                    default_estimated_duration_minutes: e.target.value,
                  })
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
                  setDraft((prev) => prev && {
                    ...prev,
                    default_min_block_duration_minutes: e.target.value,
                  })
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
                setDraft((prev) => prev && {
                  ...prev,
                  default_schedule_style: e.target.value as ScheduleStyle,
                })
              }
            >
              <option value="standalone">Standalone (default)</option>
              <option value="time_block">Time block (opt-in)</option>
              <option value="bundle">Bundle (opt-in)</option>
            </select>
          </label>
          <label className="time-map-hard-check">
            <input
              type="checkbox"
              checked={draft.auto_defer_enabled}
              onChange={(e) =>
                setDraft((prev) => prev && { ...prev, auto_defer_enabled: e.target.checked })
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
              disabled={saveMutation.isPending || !dirty}
            >
              {saveMutation.isPending ? "Saving…" : "Save scheduling defaults"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function TimeMapsSection({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const windowsQuery = useQuery({
    queryKey: ["focus-windows"],
    queryFn: fetchFocusWindows,
    enabled,
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState(EMPTY_FORM.name);
  const [formStart, setFormStart] = useState(EMPTY_FORM.start);
  const [formEnd, setFormEnd] = useState(EMPTY_FORM.end);
  const [formDays, setFormDays] = useState(EMPTY_FORM.days);
  const [formIsHard, setFormIsHard] = useState(EMPTY_FORM.isHard);
  const [showForm, setShowForm] = useState(false);

  const resetForm = () => {
    setEditingId(null);
    setFormName(EMPTY_FORM.name);
    setFormStart(EMPTY_FORM.start);
    setFormEnd(EMPTY_FORM.end);
    setFormDays([...EMPTY_FORM.days]);
    setFormIsHard(EMPTY_FORM.isHard);
  };

  const startEdit = (window: FocusWindow) => {
    setEditingId(window.id);
    setFormName(window.name);
    setFormStart(window.start_time);
    setFormEnd(window.end_time);
    setFormDays(decodeDays(window.days_of_week));
    setFormIsHard(window.is_hard);
    setShowForm(true);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const name = formName.trim();
      if (!name) throw new Error("Name is required");
      const days_of_week = encodeDays(formDays);
      if (days_of_week === 0) throw new Error("Select at least one day");
      const body = {
        name,
        start_time: formStart,
        end_time: formEnd,
        days_of_week,
        is_hard: formIsHard,
      };
      if (editingId) {
        return updateFocusWindow(editingId, body);
      }
      return createFocusWindow(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["focus-windows"] });
      emitToast(editingId ? "Time Map updated" : "Time Map created");
      resetForm();
      setShowForm(false);
    },
    onError: (err: Error) => emitToast(err.message || "Couldn't save Time Map"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteFocusWindow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["focus-windows"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      emitToast("Time Map deleted");
      if (editingId) {
        resetForm();
        setShowForm(false);
      }
    },
    onError: () => emitToast("Couldn't delete Time Map"),
  });

  const windows = windowsQuery.data ?? [];

  const toggleDay = (index: number, checked: boolean) => {
    setFormDays((prev) => {
      const next = [...prev];
      next[index] = checked;
      return next;
    });
  };

  return (
    <section className="settings-section">
      <div className="settings-section-header">
        <h3 className="settings-section-title">Time Maps</h3>
        {!showForm && (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
          >
            Add Time Map
          </button>
        )}
      </div>
      <p className="settings-help muted small">
        Preferred scheduling windows for tasks. Quick-add tokens{" "}
        <code>@morning</code>, <code>@afternoon</code>, and <code>@evening</code> match the
        default seed names when present.
      </p>
      {windowsQuery.isLoading && <p className="muted small">Loading Time Maps…</p>}
      {windows.length > 0 && (
        <ul className="time-map-list">
          {windows.map((window) => (
            <li key={window.id} className="time-map-row">
              <div className="time-map-info">
                <div className="time-map-name">{window.name}</div>
                <div className="muted small">
                  {formatTimeRange(window.start_time, window.end_time)} ·{" "}
                  {formatDaysSummary(window.days_of_week)}
                </div>
              </div>
              <span className={`time-map-badge${window.is_hard ? " hard" : ""}`}>
                {window.is_hard ? "Hard" : "Soft"}
              </span>
              <div className="time-map-actions">
                <button
                  type="button"
                  className="btn ghost small"
                  onClick={() => startEdit(window)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="btn ghost small danger-text"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(window.id)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {!windowsQuery.isLoading && windows.length === 0 && !showForm && (
        <p className="muted small">No Time Maps yet.</p>
      )}
      {showForm && (
        <form
          className="time-map-form entity-form"
          onSubmit={(e) => {
            e.preventDefault();
            saveMutation.mutate();
          }}
        >
          <label className="field">
            <span>Name</span>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="Morning Deep Work"
            />
          </label>
          <div className="time-map-time-row">
            <label className="field">
              <span>Start</span>
              <input
                type="time"
                value={formStart}
                onChange={(e) => setFormStart(e.target.value)}
              />
            </label>
            <label className="field">
              <span>End</span>
              <input
                type="time"
                value={formEnd}
                onChange={(e) => setFormEnd(e.target.value)}
              />
            </label>
          </div>
          <fieldset className="field">
            <legend>Days</legend>
            <div className="time-map-days" role="group" aria-label="Days of week">
              {DAY_BITS.map(({ label }, index) => (
                <label key={label} className="time-map-day-check">
                  <input
                    type="checkbox"
                    checked={formDays[index]}
                    onChange={(e) => toggleDay(index, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="time-map-hard-check">
            <input
              type="checkbox"
              checked={formIsHard}
              onChange={(e) => setFormIsHard(e.target.checked)}
            />
            Hard boundary (scheduler must stay inside window)
          </label>
          <div className="form-actions">
            <button
              type="button"
              className="btn secondary small"
              onClick={() => {
                resetForm();
                setShowForm(false);
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn primary small"
              disabled={saveMutation.isPending || !formName.trim()}
            >
              {saveMutation.isPending ? "Saving…" : editingId ? "Update" : "Create"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [themeId, setThemeId] = useState<ThemeId>(() => loadTheme());
  const [overrides, setOverrides] = useState<ThemeOverrides>(() => loadOverrides());
  const [draftHex, setDraftHex] = useState<Record<ThemeOverrideKey, string>>(() =>
    buildDraftHex(loadOverrides()),
  );
  const [show24h, setShow24h] = useState(() => loadShow24h());

  const accountsQuery = useQuery({
    queryKey: ["calendar-accounts"],
    queryFn: () => fetchCalendarAccounts(),
    enabled: open,
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectCalendarAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
      emitToast("Google Calendar disconnected");
    },
    onError: () => emitToast("Couldn't disconnect Google Calendar"),
  });

  const syncMutation = useMutation({
    mutationFn: (accountId: string) => syncCalendarAccount(accountId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
      queryClient.invalidateQueries({ queryKey: ["calendar-accounts"] });
      emitToast(`Synced ${result.upserted} Google event${result.upserted === 1 ? "" : "s"}`);
    },
    onError: () => emitToast("Couldn't sync Google Calendar"),
  });

  useEffect(() => {
    if (!open) return;
    const currentTheme = loadTheme();
    const currentOverrides = loadOverrides();
    setThemeId(currentTheme);
    setOverrides(currentOverrides);
    setDraftHex(buildDraftHex(currentOverrides));
    setShow24h(loadShow24h());
  }, [open]);

  const handleShow24hChange = (checked: boolean) => {
    setShow24h(checked);
    saveShow24h(checked);
    window.dispatchEvent(new CustomEvent(CALENDAR_HOURS_EVENT, { detail: checked }));
  };

  const handleThemeChange = (id: ThemeId) => {
    setThemeId(id);
    setTheme(id);
    setDraftHex(buildDraftHex(overrides));
  };

  const handleOverrideInput = (key: ThemeOverrideKey, raw: string) => {
    setDraftHex((prev) => ({ ...prev, [key]: raw }));
    if (isValidHex(raw)) {
      const normalized = normalizeHex(raw);
      const next = setOverride(key, normalized);
      setOverrides(next);
    } else if (raw.trim() === "") {
      const next = setOverride(key, undefined);
      setOverrides(next);
      setDraftHex(buildDraftHex(next));
    }
  };

  const handleResetOverrides = () => {
    const next = resetOverrides();
    setOverrides(next);
    setDraftHex(buildDraftHex(next));
  };

  return (
    <Modal open={open} title="Settings" onClose={onClose} className="settings-modal">
      <section className="settings-section">
        <h3 className="settings-section-title">Theme</h3>
        <div className="theme-preset-list" role="radiogroup" aria-label="Theme preset">
          {THEME_PRESETS.map((preset) => (
            <label key={preset.id} className="theme-preset-option">
              <input
                type="radio"
                name="theme-preset"
                value={preset.id}
                checked={themeId === preset.id}
                onChange={() => handleThemeChange(preset.id)}
              />
              <span className="theme-preset-swatch" aria-hidden>
                <span style={{ backgroundColor: preset.tokens.bg }} />
                <span style={{ backgroundColor: preset.tokens.panel }} />
                <span style={{ backgroundColor: preset.tokens.accent }} />
              </span>
              <span className="theme-preset-label">{preset.label}</span>
            </label>
          ))}
        </div>
      </section>

      <SchedulingDefaultsSection enabled={open} />

      <section className="settings-section">
        <div className="settings-section-header">
          <h3 className="settings-section-title">Custom colors</h3>
          <button
            type="button"
            className="link-btn"
            onClick={handleResetOverrides}
            disabled={Object.keys(overrides).length === 0}
          >
            Reset overrides
          </button>
        </div>
        <p className="settings-help muted small">
          Optional hex overrides for the selected preset. Leave blank to use preset values.
        </p>
        <div className="theme-override-list">
          {OVERRIDE_FIELDS.map((field) => {
            const value = draftHex[field.key];
            const preset = getThemePreset(themeId);
            const presetValue =
              field.key === "textMuted" ? preset.tokens.textMuted : preset.tokens[field.key];
            const resolved = effectiveColor(themeId, field.key, overrides);
            const invalid = value.trim() !== "" && !isValidHex(value);
            return (
              <label key={field.key} className="theme-override-row">
                <span className="theme-override-label">{field.label}</span>
                <span
                  className="theme-override-swatch"
                  style={{ backgroundColor: resolved }}
                  aria-hidden
                />
                <input
                  type="text"
                  className="theme-override-input"
                  value={value}
                  onChange={(e) => handleOverrideInput(field.key, e.target.value)}
                  placeholder={presetValue}
                  spellCheck={false}
                  autoComplete="off"
                  aria-invalid={invalid}
                />
              </label>
            );
          })}
        </div>
      </section>

      <section className="settings-section">
        <h3 className="settings-section-title">Calendar display</h3>
        <label className="calendar-display-check">
          <input
            type="checkbox"
            checked={show24h}
            onChange={(e) => handleShow24hChange(e.target.checked)}
          />
          Show 24 hours
        </label>
        <p className="settings-help muted small">
          When off, the calendar shows 6 AM–10 PM. Toggle also available in the calendar header.
        </p>
      </section>

      <TimeMapsSection enabled={open} />

      <section className="settings-section">
        <h3 className="settings-section-title">Google Calendar</h3>
        <p className="settings-help muted small">
          Connect your Google account to show external busy time on the calendar. Scopes include
          event read/write for upcoming bidirectional sync.
        </p>
        {accountsQuery.isLoading && <p className="muted small">Loading accounts…</p>}
        {(accountsQuery.data?.items ?? []).length === 0 && !accountsQuery.isLoading && (
          <button
            type="button"
            className="btn primary small"
            onClick={() => {
              window.location.href = googleCalendarConnectHref();
            }}
          >
            Connect Google Calendar
          </button>
        )}
        <ul className="calendar-account-list">
          {(accountsQuery.data?.items ?? []).map((account) => (
            <CalendarAccountRow
              key={account.id}
              account={account}
              queryClient={queryClient}
              disconnectPending={disconnectMutation.isPending}
              syncPending={syncMutation.isPending}
              onSync={() => syncMutation.mutate(account.id)}
              onDisconnect={() => disconnectMutation.mutate(account.id)}
            />
          ))}
        </ul>
        {(accountsQuery.data?.items ?? []).length > 0 && (
          <button
            type="button"
            className="btn ghost small"
            onClick={() => {
              window.location.href = googleCalendarConnectHref();
            }}
          >
            Reconnect / add account
          </button>
        )}
      </section>

      {user.is_admin && <HouseholdPanel currentUserId={user.id} />}
    </Modal>
  );
}

function buildDraftHex(overrides: ThemeOverrides): Record<ThemeOverrideKey, string> {
  return OVERRIDE_FIELDS.reduce(
    (acc, field) => {
      acc[field.key] = overrides[field.key] ?? "";
      return acc;
    },
    {} as Record<ThemeOverrideKey, string>,
  );
}
