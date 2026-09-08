import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  clearStoredAuthToken,
  getCurrentUser,
  loginAccount,
  registerAccount,
  storeAuthToken,
  type AuthMeResponse,
  type AuthUser,
} from "../api/client";
import { Permission, hasPermission as checkPermission } from "./rbac";
import type { Role } from "./rbac";

type AuthContextValue = {
  currentUser: AuthUser | null;
  authType: AuthMeResponse["auth_type"];
  loading: boolean;
  error: string;
  isRealUser: boolean;
  hasPermission: (permission: Permission) => boolean;
  login: (payload: { username_or_email: string; password: string }) => Promise<void>;
  register: (payload: { username: string; email: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readableAuthError(err: unknown): string {
  if (err instanceof ApiError) return err.detail.message;
  return err instanceof Error ? err.message : "账号操作失败。";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authType, setAuthType] = useState<AuthMeResponse["auth_type"]>("none");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const response = await getCurrentUser();
      setCurrentUser(response.user);
      setAuthType(response.auth_type);
    } catch (err) {
      setCurrentUser(null);
      setAuthType("none");
      setError(readableAuthError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function login(payload: { username_or_email: string; password: string }) {
    setError("");
    const response = await loginAccount(payload);
    storeAuthToken(response.access_token);
    setCurrentUser(response.user);
    setAuthType("user");
  }

  async function register(payload: { username: string; email: string; password: string }) {
    setError("");
    const response = await registerAccount(payload);
    storeAuthToken(response.access_token);
    setCurrentUser(response.user);
    setAuthType("user");
  }

  async function logout() {
    clearStoredAuthToken();
    await refresh();
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser,
      authType,
      loading,
      error,
      isRealUser: authType === "user",
      hasPermission: (permission: Permission) => checkPermission(currentUser?.permissions ?? [], permission),
      login,
      register,
      logout,
      refresh,
    }),
    [authType, currentUser, error, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}

export function roleLabel(role?: Role | null): string {
  if (role === "admin") return "ADMIN MODE";
  if (role === "developer") return "DEVELOPER MODE";
  if (role === "reviewer") return "REVIEWER MODE";
  return "USER MODE";
}

export { Permission };
