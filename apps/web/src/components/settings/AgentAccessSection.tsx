/**
 * Settings — Allow agent and CLI access (user_settings.allow_agent_cli_access).
 * Controls the dedicated Bearer credential channel; not Assist, not browser sessions.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSettings, updateSettings } from "../../api";
import { emitToast } from "../ToastHost";
import { AgentCredentialsManager } from "./AgentCredentialsManager";

export function AgentAccessSection({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const settingsQuery = useQuery({
    queryKey: ["user-settings"],
    queryFn: fetchSettings,
    enabled,
  });

  const toggleMutation = useMutation({
    mutationFn: (allow: boolean) => updateSettings({ allow_agent_cli_access: allow }),
    onSuccess: (result) => {
      setError(null);
      queryClient.setQueryData(["user-settings"], result);
      emitToast(
        result.allow_agent_cli_access
          ? "Agent and CLI access enabled"
          : "Agent and CLI access disabled",
      );
    },
    onError: (err: Error) => {
      // Leave query cache / checkbox on prior settings; surface inline error.
      const message = err.message || "Couldn't update agent access";
      setError(message);
      emitToast(message);
    },
  });

  const settings = settingsQuery.data;
  const allowed = settings?.allow_agent_cli_access === true;

  return (
    <section className="settings-section">
      <h3 className="settings-section-title">Agent and CLI access</h3>
      <p className="settings-help muted small">
        Controls the dedicated agent/CLI credential channel. Turning this off does not disable
        built-in Assist or ordinary browser use. It cannot stop a program that already has your
        browser session, password, or host access.
      </p>
      {settingsQuery.isLoading && <p className="muted small">Loading…</p>}
      {settingsQuery.isError && (
        <p className="form-error">Could not load agent access setting.</p>
      )}
      {settings && (
        <>
          <label className="time-map-hard-check">
            <input
              type="checkbox"
              checked={allowed}
              disabled={toggleMutation.isPending}
              onChange={(e) => {
                setError(null);
                toggleMutation.mutate(e.target.checked);
              }}
            />
            Allow agent and CLI access
          </label>
          {error && <p className="form-error">{error}</p>}
          {settings.allow_agent_cli_access_grandfathered && (
            <p className="settings-help muted small">
              This account was grandfathered on at migration; you can turn it off anytime.
            </p>
          )}
          {/* List/revoke stay mounted when allow is off; create is gated inside the manager. */}
          <AgentCredentialsManager enabled={enabled} canCreate={allowed} />
        </>
      )}
    </section>
  );
}
