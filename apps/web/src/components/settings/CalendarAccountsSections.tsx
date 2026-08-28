/**
 * Settings — Google / Microsoft calendar connect, mirror, subscriptions, sync.
 */
import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disconnectCalendarAccount,
  fetchCalendarAccounts,
  fetchCalendarSubscriptions,
  fetchGoogleCalendars,
  googleCalendarConnectHref,
  microsoftCalendarConnectHref,
  putCalendarSubscriptions,
  syncCalendarAccount,
  updateCalendarAccount,
  type CalendarAccount,
  type CalendarSubscriptionPutItem,
  type GoogleCalendarListItem,
} from "../../api";
import { emitToast } from "../ToastHost";

function calendarProviderLabel(provider: string): string {
  if (provider === "microsoft") return "Microsoft Calendar";
  if (provider === "google") return "Google Calendar";
  return "Calendar";
}

function calendarMirrorLabel(provider: string): string {
  if (provider === "microsoft") return "Push time blocks to Microsoft";
  if (provider === "google") return "Push time blocks to Google";
  return "Push time blocks to calendar";
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
    return <p className="muted small">Couldn't load calendars — try reconnecting.</p>;
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
                <span>{label}{cal.primary ? " (account primary)" : ""}</span>
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
  const [mirror, setMirror] = useState(account.mirror_blocks);

  useEffect(() => {
    setMirror(account.mirror_blocks);
  }, [account.mirror_blocks]);

  const mirrorMutation = useMutation({
    mutationFn: (value: boolean) =>
      updateCalendarAccount(account.id, { mirror_blocks: value }),
    onMutate: (value) => setMirror(value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-accounts"] });
    },
    onError: () => {
      setMirror(account.mirror_blocks);
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
          {account.account_email ?? calendarProviderLabel(account.provider)}
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
          {calendarMirrorLabel(account.provider)}
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

function CalendarProviderSection({
  title,
  help,
  connectLabel,
  connectHref,
  accounts,
  accountsLoading,
  disconnectPending,
  syncPending,
  onSync,
  onDisconnect,
  queryClient,
}: {
  title: string;
  help: string;
  connectLabel: string;
  connectHref: () => string;
  accounts: CalendarAccount[];
  accountsLoading: boolean;
  disconnectPending: boolean;
  syncPending: boolean;
  onSync: (account: CalendarAccount) => void;
  onDisconnect: (account: CalendarAccount) => void;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  return (
    <section className="settings-section">
      <h3 className="settings-section-title">{title}</h3>
      <p className="settings-help muted small">{help}</p>
      {accountsLoading && <p className="muted small">Loading accounts…</p>}
      {accounts.length === 0 && !accountsLoading && (
        <button
          type="button"
          className="btn primary small"
          onClick={() => {
            window.location.href = connectHref();
          }}
        >
          {connectLabel}
        </button>
      )}
      <ul className="calendar-account-list">
        {accounts.map((account) => (
          <CalendarAccountRow
            key={account.id}
            account={account}
            queryClient={queryClient}
            disconnectPending={disconnectPending}
            syncPending={syncPending}
            onSync={() => onSync(account)}
            onDisconnect={() => onDisconnect(account)}
          />
        ))}
      </ul>
      {accounts.length > 0 && (
        <button
          type="button"
          className="btn ghost small"
          onClick={() => {
            window.location.href = connectHref();
          }}
        >
          Reconnect / add account
        </button>
      )}
    </section>
  );
}

const GOOGLE_HELP =
  "Connect your Google account to show external busy time on the calendar. Scopes include event read/write for upcoming bidirectional sync.";
const MICROSOFT_HELP =
  "Connect your Microsoft account to show external busy time on the calendar. Scopes include event read/write for upcoming bidirectional sync.";

export function CalendarAccountsSections({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();

  const accountsQuery = useQuery({
    queryKey: ["calendar-accounts"],
    queryFn: () => fetchCalendarAccounts(),
    enabled,
  });

  const disconnectMutation = useMutation({
    mutationFn: ({ accountId }: { accountId: string; provider: string }) =>
      disconnectCalendarAccount(accountId),
    onSuccess: (_data, { provider }) => {
      queryClient.invalidateQueries({ queryKey: ["calendar-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
      emitToast(`${calendarProviderLabel(provider)} disconnected`);
    },
    onError: (_err, { provider }) =>
      emitToast(`Couldn't disconnect ${calendarProviderLabel(provider)}`),
  });

  const syncMutation = useMutation({
    mutationFn: ({ accountId }: { accountId: string; provider: string }) =>
      syncCalendarAccount(accountId),
    onSuccess: (result, { provider }) => {
      queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
      queryClient.invalidateQueries({ queryKey: ["calendar-accounts"] });
      const label = calendarProviderLabel(provider);
      emitToast(
        `Synced ${result.upserted} ${label} event${result.upserted === 1 ? "" : "s"}`,
      );
    },
    onError: (_err, { provider }) =>
      emitToast(`Couldn't sync ${calendarProviderLabel(provider)}`),
  });

  const allAccounts = accountsQuery.data?.items ?? [];
  const googleAccounts = allAccounts.filter((a) => a.provider === "google");
  const microsoftAccounts = allAccounts.filter((a) => a.provider === "microsoft");

  const onSync = (account: CalendarAccount) =>
    syncMutation.mutate({ accountId: account.id, provider: account.provider });
  const onDisconnect = (account: CalendarAccount) =>
    disconnectMutation.mutate({ accountId: account.id, provider: account.provider });

  return (
    <>
      <CalendarProviderSection
        title="Google Calendar"
        help={GOOGLE_HELP}
        connectLabel="Connect Google Calendar"
        connectHref={googleCalendarConnectHref}
        accounts={googleAccounts}
        accountsLoading={accountsQuery.isLoading}
        disconnectPending={disconnectMutation.isPending}
        syncPending={syncMutation.isPending}
        onSync={onSync}
        onDisconnect={onDisconnect}
        queryClient={queryClient}
      />
      <CalendarProviderSection
        title="Microsoft Calendar"
        help={MICROSOFT_HELP}
        connectLabel="Connect Microsoft Calendar"
        connectHref={microsoftCalendarConnectHref}
        accounts={microsoftAccounts}
        accountsLoading={accountsQuery.isLoading}
        disconnectPending={disconnectMutation.isPending}
        syncPending={syncMutation.isPending}
        onSync={onSync}
        onDisconnect={onDisconnect}
        queryClient={queryClient}
      />
    </>
  );
}
