import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disconnectCalendarAccount,
  fetchCalendarAccounts,
  fetchCalendarSubscriptions,
  fetchGoogleCalendars,
  googleCalendarConnectHref,
  putCalendarSubscriptions,
  syncCalendarAccount,
  updateCalendarAccount,
  type CalendarAccount,
  type CalendarSubscriptionPutItem,
  type GoogleCalendarListItem,
} from "../api";
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
