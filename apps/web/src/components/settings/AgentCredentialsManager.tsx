/**
 * Settings — owner agent/CLI credential mint, list, revoke (browser session only).
 * List/revoke stay available when allow is off; create is gated by canCreate.
 *
 * Create-secret UI uses a generation counter: when canCreate flips off, bump the
 * epoch so an in-flight create's late onSuccess cannot store result.secret even
 * if allow turns back on before that handler settles.
 */
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createAgentCredential,
  listAgentCredentials,
  revokeAgentCredential,
  type AgentCredential,
} from "../../api";
import { emitToast } from "../ToastHost";

const SECRET_CLEARED_ON_ALLOW_OFF =
  "Agent and CLI access was turned off — the one-time secret was cleared from this screen. Existing credentials can still be listed and revoked.";

function formatCredentialWhen(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString();
}

function credentialActionError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.code === "AGENT_ACCESS_DISABLED") {
      return "Agent and CLI access is disabled. Turn the setting on to create credentials.";
    }
    if (err.code === "AGENT_CREDENTIAL_CANNOT_ADMIN") {
      return "Credential admin requires a browser session (no Bearer on this request).";
    }
    if (err.code === "AGENT_CREDENTIAL_NOT_FOUND") {
      return "That credential was not found.";
    }
    if (err.code === "INVALID_LABEL") {
      return "Label must be 1–100 characters.";
    }
    if (err.message) {
      return err.message;
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}

type CreateMutationContext = {
  epoch: number;
};

export function AgentCredentialsManager({
  enabled,
  canCreate,
}: {
  enabled: boolean;
  canCreate: boolean;
}) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [secretClearedNotice, setSecretClearedNotice] = useState<string | null>(null);
  const [prevCanCreate, setPrevCanCreate] = useState(canCreate);
  // Bumped synchronously when canCreate flips off so late create success is suppressed.
  const createEpochRef = useRef(0);
  const [allowOffEpoch, setAllowOffEpoch] = useState(0);

  // Disabling allow is legitimate: clear any visible one-time secret and invalidate
  // in-flight create generations. List/revoke stay mounted; do not block the toggle.
  if (canCreate !== prevCanCreate) {
    setPrevCanCreate(canCreate);
    if (!canCreate) {
      createEpochRef.current += 1;
      setAllowOffEpoch(createEpochRef.current);
      if (createdSecret) {
        setCreatedSecret(null);
        setCreateError(null);
        setSecretClearedNotice(SECRET_CLEARED_ON_ALLOW_OFF);
      } else {
        setCreateError(null);
      }
    } else {
      setSecretClearedNotice(null);
    }
  }

  // Refresh the credential list on every allow-off so a create that already
  // committed server-side stays listable/revocable without exposing its secret.
  useEffect(() => {
    if (allowOffEpoch === 0) {
      return;
    }
    void queryClient.invalidateQueries({ queryKey: ["agent-credentials"] });
  }, [allowOffEpoch, queryClient]);

  const credentialsQuery = useQuery({
    queryKey: ["agent-credentials"],
    queryFn: listAgentCredentials,
    enabled,
  });

  const createMutation = useMutation({
    mutationFn: (nextLabel: string) => createAgentCredential({ label: nextLabel }),
    onMutate: (): CreateMutationContext => ({ epoch: createEpochRef.current }),
    onSuccess: (result, _label, context) => {
      // Always refresh list — credential may have been committed even when the
      // one-time secret must stay out of UI state (allow flipped off mid-flight).
      void queryClient.invalidateQueries({ queryKey: ["agent-credentials"] });
      if (!context || context.epoch !== createEpochRef.current) {
        return;
      }
      setCreateError(null);
      setSecretClearedNotice(null);
      setCreatedSecret(result.secret);
      setLabel("");
      emitToast("Agent credential created");
    },
    onError: (err: unknown, _label, context) => {
      if (!context || context.epoch !== createEpochRef.current) {
        return;
      }
      setCreateError(credentialActionError(err, "Couldn't create credential"));
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (credentialId: string) => revokeAgentCredential(credentialId),
    onSuccess: () => {
      setRevokeError(null);
      queryClient.invalidateQueries({ queryKey: ["agent-credentials"] });
      emitToast("Agent credential revoked");
    },
    onError: (err: unknown) => {
      setRevokeError(credentialActionError(err, "Couldn't revoke credential"));
    },
  });

  const dismissCreatedSecret = () => {
    setCreatedSecret(null);
    createMutation.reset();
  };

  const handleCreate = (e: FormEvent) => {
    e.preventDefault();
    if (!canCreate) {
      setCreateError("Turn on Allow agent and CLI access to create credentials.");
      return;
    }
    if (createdSecret) {
      setCreateError("Copy or dismiss the new secret before creating another credential.");
      return;
    }
    setCreateError(null);
    const trimmed = label.trim();
    if (!trimmed) {
      setCreateError("Label is required");
      return;
    }
    createMutation.mutate(trimmed);
  };

  const handleRevoke = (cred: AgentCredential) => {
    if (cred.revoked_at) {
      return;
    }
    const ok = window.confirm(
      `Revoke credential "${cred.label}"? Programs using this secret will stop working.`,
    );
    if (!ok) {
      return;
    }
    setRevokeError(null);
    revokeMutation.mutate(cred.id);
  };

  const handleCopySecret = async () => {
    if (!createdSecret) {
      return;
    }
    try {
      await navigator.clipboard.writeText(createdSecret);
      emitToast("Secret copied");
    } catch {
      emitToast("Couldn't copy — select and copy manually");
    }
  };

  const credentials = credentialsQuery.data ?? [];
  const createBlocked = !canCreate || createMutation.isPending || Boolean(createdSecret);

  return (
    <div className="agent-credentials-manager">
      <p className="settings-help muted small">
        {canCreate ? (
          <>
            Create named credentials for the CLI and other agents. Sign in with{" "}
            <code>theplan auth login --token</code> using the secret shown once at create.
          </>
        ) : (
          <>
            Access is off — new credentials cannot be created. Existing credentials can still be
            listed and revoked. Turn access on to mint a new secret.
          </>
        )}
      </p>

      {credentialsQuery.isLoading && <p className="muted small">Loading credentials…</p>}
      {credentialsQuery.isError && (
        <p className="form-error">
          Could not load credentials:{" "}
          {credentialActionError(credentialsQuery.error, "Request failed")}
        </p>
      )}

      {credentials.length > 0 && (
        <ul className="agent-credential-list">
          {credentials.map((cred) => (
            <li
              key={cred.id}
              className={`agent-credential-row${cred.revoked_at ? " revoked" : ""}`}
            >
              <div className="agent-credential-main">
                <div className="agent-credential-info">
                  <span className="agent-credential-label">
                    {cred.label}
                    {cred.revoked_at ? (
                      <span className="agent-credential-status muted"> · Revoked</span>
                    ) : null}
                  </span>
                  <span className="agent-credential-meta muted small">
                    Created {formatCredentialWhen(cred.created_at)}
                    {" · "}
                    Last used {formatCredentialWhen(cred.last_used_at)}
                    {cred.revoked_at && (
                      <>
                        {" · "}
                        Revoked {formatCredentialWhen(cred.revoked_at)}
                      </>
                    )}
                  </span>
                </div>
                {!cred.revoked_at && (
                  <button
                    type="button"
                    className="link-btn"
                    disabled={revokeMutation.isPending}
                    onClick={() => handleRevoke(cred)}
                  >
                    Revoke
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {credentialsQuery.isSuccess && credentials.length === 0 && (
        <p className="muted small">No credentials yet.</p>
      )}

      {revokeError && <p className="form-error">{revokeError}</p>}

      {secretClearedNotice && (
        <p className="settings-help muted small" role="status">
          {secretClearedNotice}
        </p>
      )}

      {createdSecret && canCreate && (
        <div className="agent-credential-secret-panel" role="status">
          <p className="agent-credential-secret-warning">
            Copy this secret now — it will not be shown again.
          </p>
          <code className="agent-credential-secret-value">{createdSecret}</code>
          <div className="form-actions">
            <button type="button" className="btn secondary" onClick={() => handleCopySecret()}>
              Copy secret
            </button>
            <button type="button" className="btn primary" onClick={dismissCreatedSecret}>
              Done
            </button>
          </div>
        </div>
      )}

      {canCreate ? (
        <form className="entity-form agent-credential-create-form" onSubmit={handleCreate}>
          <label className="field">
            <span>New credential label</span>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              autoComplete="off"
              maxLength={100}
              placeholder="e.g. laptop CLI"
              disabled={createBlocked}
            />
          </label>
          {createError && <p className="form-error">{createError}</p>}
          <div className="form-actions">
            <button
              type="submit"
              className="btn primary"
              disabled={createBlocked || !label.trim()}
            >
              {createMutation.isPending ? "Creating…" : "Create credential"}
            </button>
          </div>
        </form>
      ) : (
        <p className="muted small">Create is unavailable while agent and CLI access is off.</p>
      )}
    </div>
  );
}
