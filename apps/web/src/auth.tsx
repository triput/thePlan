import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  fetchMe,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
  type AuthLoginBody,
  type AuthRegisterBody,
  type User,
} from "./api";

export type AuthState =
  | { status: "authenticated"; user: User }
  | { status: "setup_required" }
  | { status: "unauthenticated" };

export async function fetchAuthState(signal?: AbortSignal): Promise<AuthState> {
  try {
    const user = await fetchMe(signal);
    return { status: "authenticated", user };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    if (err instanceof ApiError && err.status === 401) {
      if (err.code === "SETUP_REQUIRED") return { status: "setup_required" };
      return { status: "unauthenticated" };
    }
    throw err;
  }
}

interface AuthContextValue {
  user: User;
  login: (body: AuthLoginBody) => Promise<User>;
  register: (body: AuthRegisterBody) => Promise<User>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

interface AuthProviderProps {
  user: User;
  children: ReactNode;
}

export function AuthProvider({ user, children }: AuthProviderProps) {
  const queryClient = useQueryClient();

  const setAuthenticated = useCallback(
    (nextUser: User) => {
      const state: AuthState = { status: "authenticated", user: nextUser };
      queryClient.setQueryData(["auth", "me"], state);
      // Drop domain caches without clearing auth (clear() races a 401 refetch).
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "auth",
      });
    },
    [queryClient],
  );

  const login = useCallback(
    async (body: AuthLoginBody) => {
      const nextUser = await loginApi(body);
      setAuthenticated(nextUser);
      return nextUser;
    },
    [setAuthenticated],
  );

  const register = useCallback(
    async (body: AuthRegisterBody) => {
      const nextUser = await registerApi(body);
      setAuthenticated(nextUser);
      return nextUser;
    },
    [setAuthenticated],
  );

  const logout = useCallback(async () => {
    // Cancel first so an in-flight /auth/me cannot overwrite signed-out state.
    await queryClient.cancelQueries({ queryKey: ["auth", "me"] });
    const state: AuthState = { status: "unauthenticated" };
    queryClient.setQueryData(["auth", "me"], state);
    queryClient.removeQueries({
      predicate: (query) => query.queryKey[0] !== "auth",
    });
    try {
      await logoutApi();
    } catch {
      // Local session already cleared; cookie may linger until expiry.
    }
  }, [queryClient]);

  const refreshAuth = useCallback(async () => {
    const state = await fetchAuthState();
    queryClient.setQueryData(["auth", "me"], state);
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, login, register, logout, refreshAuth }),
    [user, login, register, logout, refreshAuth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthQuery() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: ({ signal }) => fetchAuthState(signal),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}
