import { useState, type FormEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AuthProvider,
  useAuth,
  useAuthQuery,
  type AuthState,
} from "../auth";
import {
  ApiError,
  login as loginApi,
  register as registerApi,
  updateMe,
  type User,
} from "../api";

const PASSWORD_HINT = "12+ characters; spaces OK for passphrases";

interface AuthGateProps {
  children: ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const authQuery = useAuthQuery();

  // Prefer cached auth state over a loading flash (e.g. after sign-out).
  if (authQuery.isPending && !authQuery.data) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <p className="muted">Loading…</p>
        </div>
      </div>
    );
  }

  if (authQuery.isError) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h1 className="auth-title">thePlan</h1>
          <p className="form-error">
            Could not reach the server: {(authQuery.error as Error).message}
          </p>
          <button
            type="button"
            className="btn primary"
            onClick={() => void authQuery.refetch()}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const state = authQuery.data!;

  if (state.status === "setup_required") {
    return <SetupScreen />;
  }

  if (state.status === "unauthenticated") {
    return <LoginScreen />;
  }

  return (
    <AuthProvider user={state.user}>
      {state.user.must_change_password ? (
        <MustChangePasswordScreen />
      ) : (
        children
      )}
    </AuthProvider>
  );
}

function useUnauthenticatedAuthActions() {
  const queryClient = useQueryClient();

  const setAuthenticated = (user: User) => {
    const state: AuthState = { status: "authenticated", user };
    queryClient.setQueryData(["auth", "me"], state);
    queryClient.removeQueries({
      predicate: (query) => query.queryKey[0] !== "auth",
    });
  };

  return {
    login: async (body: { identifier: string; password: string }) => {
      const user = await loginApi(body);
      setAuthenticated(user);
      return user;
    },
    register: async (body: {
      username: string;
      email: string;
      password: string;
      display_name?: string | null;
    }) => {
      const user = await registerApi(body);
      setAuthenticated(user);
      return user;
    },
  };
}

function SetupScreen() {
  const { register } = useUnauthenticatedAuthActions();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await register({
        username: username.trim(),
        email: email.trim(),
        password,
        display_name: displayName.trim() || null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1 className="auth-title">Welcome to thePlan</h1>
        <p className="auth-subtitle muted">
          Create the first household account to get started.
        </p>
        <form className="entity-form auth-form" onSubmit={(e) => void handleSubmit(e)}>
          <label className="field">
            <span>Username</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
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
              autoComplete="name"
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="form-actions stacked">
            <button type="submit" className="btn primary" disabled={pending}>
              {pending ? "Creating account…" : "Create account"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function LoginScreen() {
  const { login } = useUnauthenticatedAuthActions();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login({ identifier: identifier.trim(), password });
    } catch (err) {
      if (err instanceof ApiError && err.code === "INVALID_CREDENTIALS") {
        setError("Invalid username, email, or password.");
      } else {
        setError(err instanceof Error ? err.message : "Login failed");
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1 className="auth-title">Sign in</h1>
        <p className="auth-subtitle muted">Sign in to your thePlan household.</p>
        <form className="entity-form auth-form" onSubmit={(e) => void handleSubmit(e)}>
          <label className="field">
            <span>Username or email</span>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </label>
          <label className="field">
            <span>Password or passphrase</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
            <span className="field-hint muted small">{PASSWORD_HINT}</span>
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="form-actions stacked">
            <button type="submit" className="btn primary" disabled={pending}>
              {pending ? "Signing in…" : "Sign in"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function MustChangePasswordScreen() {
  const { logout } = useAuth();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const nextUser = await updateMe({ password });
      const state: AuthState = { status: "authenticated", user: nextUser };
      queryClient.setQueryData(["auth", "me"], state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update password");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1 className="auth-title">Choose a new password</h1>
        <p className="auth-subtitle muted">
          Your account requires a new password before you can use thePlan.
        </p>
        <form className="entity-form auth-form" onSubmit={(e) => void handleSubmit(e)}>
          <label className="field">
            <span>New password or passphrase</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
              autoFocus
            />
            <span className="field-hint muted small">{PASSWORD_HINT}</span>
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="form-actions stacked">
            <button type="submit" className="btn primary" disabled={pending}>
              {pending ? "Saving…" : "Update password"}
            </button>
            <button
              type="button"
              className="btn ghost"
              disabled={pending}
              onClick={() => void logout()}
            >
              Sign out
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
