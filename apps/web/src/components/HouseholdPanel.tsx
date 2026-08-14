import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createUser,
  fetchUsers,
  updateUser,
  type AuthUserAdmin,
} from "../api";

const PASSWORD_HINT = "12+ characters; spaces OK for passphrases";

interface HouseholdPanelProps {
  currentUserId: string;
}

export function HouseholdPanel({ currentUserId }: HouseholdPanelProps) {
  const queryClient = useQueryClient();
  const usersQuery = useQuery({
    queryKey: ["auth", "users"],
    queryFn: fetchUsers,
  });

  const [showCreate, setShowCreate] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [passwordUserId, setPasswordUserId] = useState<string | null>(null);
  const [emailUserId, setEmailUserId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "users"] });
      setUsername("");
      setEmail("");
      setPassword("");
      setDisplayName("");
      setCreateError(null);
      setShowCreate(false);
    },
    onError: (err: Error) => setCreateError(err.message),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ userId, isDisabled }: { userId: string; isDisabled: boolean }) =>
      updateUser(userId, { is_disabled: isDisabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "users"] });
    },
  });

  const passwordMutation = useMutation({
    mutationFn: ({ userId, password: next }: { userId: string; password: string }) =>
      updateUser(userId, { password: next }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "users"] });
      setPasswordUserId(null);
    },
  });

  const emailMutation = useMutation({
    mutationFn: ({ userId, email: next }: { userId: string; email: string }) =>
      updateUser(userId, { email: next }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "users"] });
      setEmailUserId(null);
    },
  });

  const handleCreate = (e: FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    createMutation.mutate({
      username: username.trim(),
      email: email.trim(),
      password,
      display_name: displayName.trim() || null,
    });
  };

  const users = usersQuery.data ?? [];

  return (
    <section className="settings-section">
      <div className="settings-section-header">
        <h3 className="settings-section-title">Household</h3>
        {!showCreate && (
          <button
            type="button"
            className="link-btn"
            onClick={() => setShowCreate(true)}
          >
            Add user
          </button>
        )}
      </div>
      <p className="settings-help muted small">
        Manage household members who can sign in to this thePlan instance. You can set a
        new password for any account (including your own).
      </p>

      {usersQuery.isLoading && <p className="muted small">Loading users…</p>}
      {usersQuery.isError && (
        <p className="form-error">
          Failed to load users: {(usersQuery.error as Error).message}
        </p>
      )}

      {users.length > 0 && (
        <ul className="household-user-list">
          {users.map((user) => (
            <HouseholdUserRow
              key={user.id}
              user={user}
              isSelf={user.id === currentUserId}
              showPasswordForm={passwordUserId === user.id}
              showEmailForm={emailUserId === user.id}
              onTogglePasswordForm={() => {
                setEmailUserId(null);
                setPasswordUserId((current) => (current === user.id ? null : user.id));
              }}
              onToggleEmailForm={() => {
                setPasswordUserId(null);
                setEmailUserId((current) => (current === user.id ? null : user.id));
              }}
              onToggleDisabled={(isDisabled) =>
                toggleMutation.mutate({ userId: user.id, isDisabled })
              }
              onSetPassword={(next) =>
                passwordMutation.mutateAsync({ userId: user.id, password: next })
              }
              onSetEmail={(next) =>
                emailMutation.mutateAsync({ userId: user.id, email: next })
              }
              togglePending={toggleMutation.isPending}
              passwordPending={passwordMutation.isPending && passwordUserId === user.id}
              emailPending={emailMutation.isPending && emailUserId === user.id}
              passwordError={
                passwordMutation.isError && passwordUserId === user.id
                  ? (passwordMutation.error as Error).message
                  : null
              }
              emailError={
                emailMutation.isError && emailUserId === user.id
                  ? (emailMutation.error as Error).message
                  : null
              }
            />
          ))}
        </ul>
      )}

      {showCreate && (
        <form className="entity-form household-create-form" onSubmit={handleCreate}>
          <label className="field">
            <span>Username</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="off"
              required
            />
          </label>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
              required
            />
          </label>
          <label className="field">
            <span>Password or passphrase</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
            <span className="field-hint muted small">{PASSWORD_HINT}</span>
          </label>
          <label className="field">
            <span>Display name (optional)</span>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              autoComplete="off"
            />
          </label>
          {createError && <p className="form-error">{createError}</p>}
          <div className="form-actions">
            <button
              type="button"
              className="btn secondary"
              onClick={() => {
                setShowCreate(false);
                setCreateError(null);
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn primary"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "Creating…" : "Create user"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function HouseholdUserRow({
  user,
  isSelf,
  showPasswordForm,
  showEmailForm,
  onTogglePasswordForm,
  onToggleEmailForm,
  onToggleDisabled,
  onSetPassword,
  onSetEmail,
  togglePending,
  passwordPending,
  emailPending,
  passwordError,
  emailError,
}: {
  user: AuthUserAdmin;
  isSelf: boolean;
  showPasswordForm: boolean;
  showEmailForm: boolean;
  onTogglePasswordForm: () => void;
  onToggleEmailForm: () => void;
  onToggleDisabled: (isDisabled: boolean) => void;
  onSetPassword: (password: string) => Promise<unknown>;
  onSetEmail: (email: string) => Promise<unknown>;
  togglePending: boolean;
  passwordPending: boolean;
  emailPending: boolean;
  passwordError: string | null;
  emailError: string | null;
}) {
  const [newPassword, setNewPassword] = useState("");
  const [newEmail, setNewEmail] = useState(user.email);
  const [localPasswordError, setLocalPasswordError] = useState<string | null>(null);
  const [localEmailError, setLocalEmailError] = useState<string | null>(null);
  const label = user.display_name ?? user.username ?? user.email;
  const sublabel = user.display_name
    ? (user.username ?? user.email)
    : user.email;

  const handlePasswordSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalPasswordError(null);
    try {
      await onSetPassword(newPassword);
      setNewPassword("");
    } catch (err) {
      setLocalPasswordError(err instanceof Error ? err.message : "Failed to set password");
    }
  };

  const handleEmailSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalEmailError(null);
    try {
      await onSetEmail(newEmail.trim());
    } catch (err) {
      if (err instanceof ApiError && err.code === "EMAIL_TAKEN") {
        setLocalEmailError("That email is already in use.");
      } else {
        setLocalEmailError(err instanceof Error ? err.message : "Failed to update email");
      }
    }
  };

  return (
    <li className={`household-user-row${user.is_disabled ? " disabled" : ""}`}>
      <div className="household-user-main">
        <div className="household-user-info">
          <span className="household-user-name">{label}</span>
          <span className="household-user-meta muted small">
            {sublabel}
            {user.is_admin && " · Admin"}
            {user.is_disabled && " · Disabled"}
            {user.must_change_password && " · Must change password"}
            {isSelf && " · You"}
          </span>
        </div>
        <div className="household-user-actions">
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              setNewEmail(user.email);
              setLocalEmailError(null);
              onToggleEmailForm();
            }}
          >
            {showEmailForm ? "Cancel" : "Edit email"}
          </button>
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              setNewPassword("");
              setLocalPasswordError(null);
              onTogglePasswordForm();
            }}
          >
            {showPasswordForm ? "Cancel" : "Set password"}
          </button>
          <label className="household-toggle">
            <input
              type="checkbox"
              checked={!user.is_disabled}
              disabled={togglePending || isSelf}
              onChange={(e) => onToggleDisabled(!e.target.checked)}
              title={isSelf ? "You cannot disable your own account" : "Enable or disable account"}
            />
            <span className="small">{user.is_disabled ? "Disabled" : "Active"}</span>
          </label>
        </div>
      </div>

      {showEmailForm && (
        <form className="entity-form household-email-form" onSubmit={(e) => void handleEmailSubmit(e)}>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              autoComplete="off"
              required
              autoFocus
            />
          </label>
          {(localEmailError || emailError) && (
            <p className="form-error">{localEmailError ?? emailError}</p>
          )}
          <div className="form-actions">
            <button type="submit" className="btn primary small" disabled={emailPending}>
              {emailPending ? "Saving…" : "Save email"}
            </button>
          </div>
        </form>
      )}

      {showPasswordForm && (
        <form className="entity-form household-password-form" onSubmit={(e) => void handlePasswordSubmit(e)}>
          <p className="settings-help muted small">
            Setting a password requires that user to change it on their next sign-in.
          </p>
          <label className="field">
            <span>New password or passphrase</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
              autoFocus={!showEmailForm}
            />
            <span className="field-hint muted small">{PASSWORD_HINT}</span>
          </label>
          {(localPasswordError || passwordError) && (
            <p className="form-error">{localPasswordError ?? passwordError}</p>
          )}
          <div className="form-actions">
            <button type="submit" className="btn primary small" disabled={passwordPending}>
              {passwordPending ? "Saving…" : "Save password"}
            </button>
          </div>
        </form>
      )}
    </li>
  );
}
