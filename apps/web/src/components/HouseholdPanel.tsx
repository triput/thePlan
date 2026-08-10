import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
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
        Manage household members who can sign in to this thePlan instance.
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
              onToggleDisabled={(isDisabled) =>
                toggleMutation.mutate({ userId: user.id, isDisabled })
              }
              togglePending={toggleMutation.isPending}
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
  onToggleDisabled,
  togglePending,
}: {
  user: AuthUserAdmin;
  isSelf: boolean;
  onToggleDisabled: (isDisabled: boolean) => void;
  togglePending: boolean;
}) {
  const label = user.display_name ?? user.username ?? user.email;
  const sublabel = user.display_name
    ? (user.username ?? user.email)
    : user.email;

  return (
    <li className={`household-user-row${user.is_disabled ? " disabled" : ""}`}>
      <div className="household-user-info">
        <span className="household-user-name">{label}</span>
        <span className="household-user-meta muted small">
          {sublabel}
          {user.is_admin && " · Admin"}
          {user.is_disabled && " · Disabled"}
        </span>
      </div>
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
    </li>
  );
}
