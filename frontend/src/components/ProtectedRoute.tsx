import type { ReactNode } from "react";

import { useAuth } from "../auth/AuthContext";
import type { Permission } from "../auth/rbac";
import AccessDenied from "../pages/AccessDenied";

type ProtectedRouteProps = {
  children: ReactNode;
  permission?: Permission;
  anyPermission?: Permission[];
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { currentUser, loading } = useAuth();
  if (loading) return <section className="placeholder-panel">正在检查账号权限...</section>;
  if (!currentUser) return <AccessDenied />;
  return <>{children}</>;
}

export function PermissionRoute({ children, permission, anyPermission }: ProtectedRouteProps) {
  const { currentUser, hasPermission, loading } = useAuth();
  if (loading) return <section className="placeholder-panel">正在检查账号权限...</section>;
  if (!currentUser) return <AccessDenied />;
  const allowed = permission
    ? hasPermission(permission)
    : anyPermission?.some((item) => hasPermission(item)) ?? true;
  if (!allowed) return <AccessDenied />;
  return <>{children}</>;
}
