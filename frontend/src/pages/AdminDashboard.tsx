import { type FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  createAdminUser,
  getAdminAuditLog,
  getAdminSystemStatus,
  getProductionStatus,
  listAdminUsers,
  publishProductionKnowledge,
  rollbackProductionKnowledge,
  updateAdminUser,
  type AdminAuditLogItem,
  type AdminSystemStatus,
  type AuthUser,
  type ProductionStatusResponse,
} from "../api/client";
import { Role, type Role as RoleValue } from "../auth/rbac";

const ROLES: RoleValue[] = [Role.USER, Role.REVIEWER, Role.DEVELOPER, Role.ADMIN];

function readableError(err: unknown): string {
  if (err instanceof ApiError) return err.detail.message;
  return err instanceof Error ? err.message : "管理员操作失败。";
}

export default function AdminDashboard() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [system, setSystem] = useState<AdminSystemStatus | null>(null);
  const [production, setProduction] = useState<ProductionStatusResponse | null>(null);
  const [auditLog, setAuditLog] = useState<AdminAuditLogItem[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [newUser, setNewUser] = useState({
    username: "",
    email: "",
    password: "",
    role: Role.REVIEWER as RoleValue,
  });

  async function refresh() {
    setLoading(true);
    setMessage("");
    try {
      const [usersResponse, systemResponse, productionResponse, auditResponse] = await Promise.all([
        listAdminUsers(),
        getAdminSystemStatus(),
        getProductionStatus(),
        getAdminAuditLog(),
      ]);
      setUsers(usersResponse.items);
      setSystem(systemResponse);
      setProduction(productionResponse);
      setAuditLog(auditResponse.items);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      await createAdminUser({ ...newUser, is_active: true });
      setNewUser({ username: "", email: "", password: "", role: Role.REVIEWER });
      await refresh();
      setMessage("用户已创建。");
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  async function updateRole(user: AuthUser, role: RoleValue) {
    setLoading(true);
    setMessage("");
    try {
      await updateAdminUser(user.id, { role });
      await refresh();
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  async function toggleActive(user: AuthUser) {
    setLoading(true);
    setMessage("");
    try {
      await updateAdminUser(user.id, { is_active: !user.is_active });
      await refresh();
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  async function publishDryRun() {
    setLoading(true);
    try {
      const result = await publishProductionKnowledge({ dry_run: true });
      setMessage(`Production publish dry-run: ${JSON.stringify(result)}`);
      await refresh();
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  async function rollbackDryRun() {
    setLoading(true);
    try {
      const result = await rollbackProductionKnowledge({ dry_run: true });
      setMessage(`Production rollback dry-run: ${JSON.stringify(result)}`);
      await refresh();
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-stack admin-page">
      <div className="section-heading wide-heading">
        <span className="eyebrow">Admin Mode</span>
        <h1>Administration</h1>
        <p>管理用户、角色、系统状态与 Production Knowledge Base。普通用户聊天内容不在此页面展示。</p>
      </div>

      {message && <div className={message.includes("失败") || message.includes("保留") ? "error-banner" : "notice-band"}>{message}</div>}

      <section className="review-layout">
        <section className="result-card">
          <h2>Users & Roles</h2>
          <form className="admin-create-user" onSubmit={createUser}>
            <input
              onChange={(event) => setNewUser((current) => ({ ...current, username: event.target.value }))}
              placeholder="username"
              value={newUser.username}
            />
            <input
              onChange={(event) => setNewUser((current) => ({ ...current, email: event.target.value }))}
              placeholder="email"
              value={newUser.email}
            />
            <input
              onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))}
              placeholder="password"
              type="password"
              value={newUser.password}
            />
            <select
              onChange={(event) => setNewUser((current) => ({ ...current, role: event.target.value as RoleValue }))}
              value={newUser.role}
            >
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
            <button className="primary-button" disabled={loading} type="submit">
              创建用户
            </button>
          </form>

          <div className="compact-table">
            {users.map((user) => (
              <article key={user.id}>
                <div>
                  <strong>{user.username}</strong>
                  <span>{user.email}</span>
                </div>
                <small>{user.is_active ? "active" : "inactive"} · {user.id.slice(0, 8)}</small>
                <div className="compact-actions">
                  <select onChange={(event) => updateRole(user, event.target.value as RoleValue)} value={user.role}>
                    {ROLES.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                  <button disabled={loading} onClick={() => toggleActive(user)} type="button">
                    {user.is_active ? "禁用" : "激活"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="result-card">
          <h2>System Status</h2>
          <pre>{JSON.stringify(system, null, 2)}</pre>
        </section>
      </section>

      <section className="review-layout">
        <section className="result-card">
          <h2>Production Knowledge Base</h2>
          <div className="compact-actions">
            <button disabled={loading} onClick={publishDryRun} type="button">
              Publish Dry Run
            </button>
            <button disabled={loading} onClick={rollbackDryRun} type="button">
              Rollback Dry Run
            </button>
          </div>
          <pre>{JSON.stringify(production, null, 2)}</pre>
        </section>

        <section className="result-card">
          <h2>Admin Audit Log</h2>
          <div className="compact-table">
            {auditLog.slice(0, 20).map((item) => (
              <article key={item.audit_id}>
                <div>
                  <strong>{item.action}</strong>
                  <span>{new Date(item.created_at).toLocaleString()}</span>
                </div>
                <small>{item.target_type} · {item.target_id}</small>
              </article>
            ))}
          </div>
        </section>
      </section>

      <button className="primary-button" disabled={loading} onClick={refresh} type="button">
        {loading ? "刷新中..." : "刷新"}
      </button>
    </section>
  );
}
