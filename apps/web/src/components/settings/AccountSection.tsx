/**
 * Settings — Account self-service (display name / email / password).
 * ADR-007; PATCH /auth/me — not user_settings.
 */
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, updateMe, type AuthMeUpdateBody } from "../../api";
import { useAuth } from "../../auth";
import { emitToast } from "../ToastHost";

const PASSWORD_HINT = "12+ characters; spaces OK for passphrases";

export function AccountSection({ enabled }: { enabled: boolean }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    setDisplayName(user.display_name ?? "");
    setEmail(user.email);
    setPassword("");
    setError(null);
  }, [enabled, user.display_name, user.email]);

  const dirty =
    displayName.trim() !== (user.display_name ?? "") ||
    email.trim() !== user.email ||
    password.length > 0;

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body: AuthMeUpdateBody = {};
      const trimmedDisplay = displayName.trim();
      const trimmedEmail = email.trim();
      const currentDisplay = user.display_name ?? "";
      if (trimmedDisplay !== currentDisplay) {
        body.display_name = trimmedDisplay || null;
      }
      if (trimmedEmail !== user.email) {
        body.email = trimmedEmail;
      }
      if (password) {
        body.password = password;
      }
      if (Object.keys(body).length === 0) return null;
      return updateMe(body);
    },
    onSuccess: (nextUser) => {
      if (nextUser) {
        queryClient.setQueryData(["auth", "me"], { status: "authenticated", user: nextUser });
        setPassword("");
        setError(null);
        emitToast("Account updated");
      }
    },
    onError: (err: Error) => {
      if (err instanceof ApiError && err.code === "EMAIL_TAKEN") {
        setError("That email is already in use.");
      } else {
        setError(err.message || "Couldn't save account");
      }
    },
  });

  return (
    <section className="settings-section">
      <h3 className="settings-section-title">Account</h3>
      <p className="settings-help muted small">
        Update your display name, email, or password.
      </p>
      <form
        className="entity-form account-form"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          saveMutation.mutate();
        }}
      >
        <div className="field account-username-field">
          <span>Username</span>
          <p className="account-username-value">{user.username ?? "—"}</p>
          <span className="field-hint muted small">Cannot be changed</span>
        </div>
        <label className="field">
          <span>Display name</span>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="name"
          />
        </label>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label className="field">
          <span>New password (optional)</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={password ? 12 : undefined}
          />
          <span className="field-hint muted small">{PASSWORD_HINT}</span>
        </label>
        {error && <p className="form-error">{error}</p>}
        <div className="form-actions">
          <button
            type="submit"
            className="btn primary small"
            disabled={saveMutation.isPending || !dirty}
          >
            {saveMutation.isPending ? "Saving…" : "Save account"}
          </button>
        </div>
      </form>
    </section>
  );
}
