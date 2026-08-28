/**
 * Settings — Assist (SLM) reachability status. ADR-010; read-only.
 */
import { useQuery } from "@tanstack/react-query";
import { fetchAssistStatus } from "../../api";

export function AssistStatusSection({ enabled }: { enabled: boolean }) {
  const statusQuery = useQuery({
    queryKey: ["assist-status"],
    queryFn: fetchAssistStatus,
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  return (
    <section className="settings-section">
      <h3 className="settings-section-title">Assist (SLM)</h3>
      <p className="settings-help muted small">
        Local Ollama via OpenAI-compatible HTTP. Host/model are server env (
        <code>ASSIST_BASE_URL</code>, <code>ASSIST_MODEL</code>). Review→confirm in the Assist panel —
        never blocks CRUD when the model is down.
      </p>
      {statusQuery.isLoading && <p className="muted small">Checking Assist…</p>}
      {statusQuery.isError && (
        <p className="form-error">Could not load Assist status.</p>
      )}
      {statusQuery.data && (
        <p className="muted small">
          Reachable: <strong>{statusQuery.data.reachable ? "yes" : "no"}</strong>
          {" · "}
          Model: <code>{statusQuery.data.model}</code>
          {" · "}
          Base: <code>{statusQuery.data.base_url}</code>
          {statusQuery.data.detail ? ` · ${statusQuery.data.detail}` : null}
        </p>
      )}
    </section>
  );
}
