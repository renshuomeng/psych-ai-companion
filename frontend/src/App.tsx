import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  getAuthSession,
  logoutAccess,
  submitAccessCode,
  type AuthSessionResponse,
  type CheckIn,
} from "./api/client";
import { PermissionRoute, ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth, roleLabel } from "./auth/AuthContext";
import { Permission } from "./auth/rbac";
import CheckInPage from "./pages/CheckIn";
import Home from "./pages/Home";
import MultimodalChat from "./pages/MultimodalChat";
import Relaxation from "./pages/Relaxation";
import Report from "./pages/Report";
import VideoCompanion from "./pages/VideoCompanion";
import EvaluationDashboard from "./pages/EvaluationDashboard";
import AccessDenied from "./pages/AccessDenied";
import AdminDashboard from "./pages/AdminDashboard";
import DeveloperDashboard from "./pages/DeveloperDashboard";
import HumanEvaluationReview from "./pages/HumanEvaluationReview";
import KnowledgeReview from "./pages/KnowledgeReview";

type Page =
  | "home"
  | "checkin"
  | "multimodal"
  | "relaxation"
  | "report"
  | "video"
  | "knowledge"
  | "humanEvaluation"
  | "evaluation"
  | "developer"
  | "admin";

const DEFAULT_CHECKIN: CheckIn = {
  stress_score: 5,
  stress_source: [],
  preferred_style: "温和陪伴",
};

const NAV_ITEMS: { key: Page; label: string; permission?: Permission }[] = [
  { key: "home", label: "首页" },
  { key: "checkin", label: "情绪打卡" },
  { key: "multimodal", label: "心语陪伴" },
  { key: "relaxation", label: "放松练习" },
  { key: "report", label: "趋势报告" },
  { key: "video", label: "视频陪伴" },
  { key: "knowledge", label: "Knowledge Review", permission: Permission.KNOWLEDGE_REVIEW },
  { key: "humanEvaluation", label: "Human Evaluation", permission: Permission.EVALUATION_REVIEW },
  { key: "evaluation", label: "Evaluation Center", permission: Permission.EVALUATION_RUN_CREATE },
  { key: "developer", label: "Developer", permission: Permission.RAG_DEBUG_VIEW },
  { key: "admin", label: "Administration", permission: Permission.USER_MANAGE },
];

function initialPage(): Page {
  if (window.location.pathname.startsWith("/knowledge/review")) return "knowledge";
  if (window.location.pathname.startsWith("/evaluation/review")) return "humanEvaluation";
  if (window.location.pathname.startsWith("/evaluation")) return "evaluation";
  if (window.location.pathname.startsWith("/developer")) return "developer";
  if (window.location.pathname.startsWith("/admin")) return "admin";
  if (window.location.pathname.startsWith("/chat")) return "multimodal";
  return "home";
}

function AccessGate({ onUnlocked }: { onUnlocked: (session: AuthSessionResponse) => void }) {
  const [accessCode, setAccessCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const session = await submitAccessCode(accessCode);
      onUnlocked(session);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail.message);
      } else {
        setError(err instanceof Error ? err.message : "访问验证失败。");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="access-page">
      <section className="access-panel">
        <span className="eyebrow">Public Demo</span>
        <h1>AI 心理陪伴 Web 系统</h1>
        <p>
          这是竞赛公网演示入口。系统会调用豆包/火山方舟能力，使用前需要输入演示访问码。
          本系统不进行医学诊断，不替代专业心理或医疗服务。
        </p>
        <form className="access-form" onSubmit={submit}>
          <label className="field-label" htmlFor="access-code">
            演示访问码
          </label>
          <input
            autoComplete="one-time-code"
            disabled={submitting}
            id="access-code"
            onChange={(event) => setAccessCode(event.target.value)}
            placeholder="请输入老师或演示者提供的访问码"
            type="password"
            value={accessCode}
          />
          {error && <div className="error-banner">{error}</div>}
          <button className="primary-button" disabled={submitting || !accessCode.trim()} type="submit">
            {submitting ? "验证中..." : "进入演示系统"}
          </button>
        </form>
      </section>
    </main>
  );
}

function AccountPanel() {
  const auth = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");
    try {
      if (mode === "login") {
        await auth.login({ username_or_email: usernameOrEmail, password });
      } else {
        await auth.register({ username, email, password });
      }
      setPassword("");
      setMessage("账号已切换。");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.detail.message : err instanceof Error ? err.message : "账号操作失败。");
    } finally {
      setSubmitting(false);
    }
  }

  const currentRole = auth.currentUser?.role ?? "user";

  return (
    <section className="account-panel">
      <div>
        <span className="eyebrow">{roleLabel(currentRole)}</span>
        <strong>{auth.currentUser?.username ?? "未登录"}</strong>
        <small>{auth.isRealUser ? auth.currentUser?.email : "本地/演示 user mode"}</small>
      </div>
      {auth.isRealUser ? (
        <button disabled={submitting} onClick={() => void auth.logout()} type="button">
          退出账号
        </button>
      ) : (
        <form className="account-form" onSubmit={submit}>
          <div className="segmented-control">
            <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
              登录
            </button>
            <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} type="button">
              注册
            </button>
          </div>
          {mode === "login" ? (
            <input
              onChange={(event) => setUsernameOrEmail(event.target.value)}
              placeholder="用户名或邮箱"
              value={usernameOrEmail}
            />
          ) : (
            <>
              <input onChange={(event) => setUsername(event.target.value)} placeholder="用户名" value={username} />
              <input onChange={(event) => setEmail(event.target.value)} placeholder="邮箱" value={email} />
            </>
          )}
          <input
            onChange={(event) => setPassword(event.target.value)}
            placeholder="密码"
            type="password"
            value={password}
          />
          <button disabled={submitting || !password.trim()} type="submit">
            {submitting ? "处理中..." : mode === "login" ? "登录账号" : "创建 user"}
          </button>
          {message && <small className="inline-error">{message}</small>}
        </form>
      )}
    </section>
  );
}

function readSavedCheckIn(): CheckIn {
  const raw = localStorage.getItem("psych-ai-checkin");
  if (!raw) return DEFAULT_CHECKIN;

  try {
    return { ...DEFAULT_CHECKIN, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_CHECKIN;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function readableBackendError(err: unknown): string {
  if (err instanceof ApiError) {
    return err.detail.message;
  }
  if (err instanceof DOMException && (err.name === "AbortError" || err.name === "TimeoutError")) {
    return "请求超时或后端正在重启，请稍后重试。";
  }
  if (err instanceof TypeError && /fetch|network|failed/i.test(err.message)) {
    return "浏览器无法连接后端，请确认 8001 后端服务正在运行。";
  }
  const message = err instanceof Error ? err.message : String(err || "unknown error");
  if (/aborted|abort|signal/i.test(message)) {
    return "请求被中断，通常是后端刚刚重启或接口暂时未就绪。";
  }
  return message;
}

async function getAuthSessionWithRetry(attempts = 3): Promise<AuthSessionResponse> {
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await getAuthSession();
    } catch (err) {
      lastError = err;
      if (attempt < attempts) {
        await sleep(600 * attempt);
      }
    }
  }
  throw lastError;
}

export default function App() {
  const auth = useAuth();
  const [page, setPage] = useState<Page>(initialPage);
  const [checkin, setCheckin] = useState<CheckIn>(readSavedCheckIn);
  const [authSession, setAuthSession] = useState<AuthSessionResponse | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    localStorage.setItem("psych-ai-checkin", JSON.stringify(checkin));
  }, [checkin]);

  function refreshAuthSession() {
    setAuthLoading(true);
    setAuthError("");
    void getAuthSessionWithRetry()
      .then(setAuthSession)
      .catch((err) => {
        setAuthSession({
          authenticated: false,
          access_required: true,
          expires_at: null,
        });
        const message = readableBackendError(err);
        setAuthError(`后端服务暂时无响应，请确认 8001 后端已经启动后再重试。错误：${message}`);
      })
      .finally(() => setAuthLoading(false));
  }

  useEffect(() => {
    refreshAuthSession();
  }, []);

  const permissionKey = auth.currentUser?.permissions.join("|") ?? "";
  const visibleNavItems = useMemo(
    () => NAV_ITEMS.filter((item) => !item.permission || auth.hasPermission(item.permission)),
    [permissionKey],
  );

  useEffect(() => {
    if (!visibleNavItems.some((item) => item.key === page)) {
      setPage("home");
    }
  }, [page, visibleNavItems]);

  useEffect(() => {
    function onPopState() {
      setPage(initialPage());
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  async function logout() {
    const session = await logoutAccess().catch(() => ({
      authenticated: false,
      access_required: true,
      expires_at: null,
    }));
    setAuthSession(session);
    await auth.refresh();
  }

  if (authLoading) {
    return (
      <main className="access-page">
        <section className="access-panel">
          <span className="eyebrow">Loading</span>
          <h1>正在检查演示访问状态</h1>
          <p>请稍候。</p>
        </section>
      </main>
    );
  }

  if (authError) {
    return (
      <main className="access-page">
        <section className="access-panel">
          <span className="eyebrow">Backend</span>
          <h1>后端连接暂时无响应</h1>
          <p>{authError}</p>
          <button className="primary-button" onClick={refreshAuthSession} type="button">
            重新检查
          </button>
        </section>
      </main>
    );
  }

  if (authSession?.access_required && !authSession.authenticated) {
    return (
      <AccessGate
        onUnlocked={(session) => {
          setAuthSession(session);
          void auth.refresh();
        }}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark">AI</span>
          <div>
            <strong>心理陪伴</strong>
            <span>安全闭环演示版</span>
          </div>
        </div>
        <div className="demo-status">
          <span>{authSession?.access_required ? "访问码已验证" : "本地开发模式"}</span>
          {authSession?.expires_at && <small>会话有效至 {new Date(authSession.expires_at).toLocaleString()}</small>}
          {authSession?.access_required && (
            <button onClick={logout} type="button">
              退出访问
            </button>
          )}
        </div>

        <AccountPanel />

        <nav className="nav-list" aria-label="主导航">
          {visibleNavItems.map((item) => (
            <button
              className={page === item.key ? "nav-button active" : "nav-button"}
              key={item.key}
              onClick={() => {
                setPage(item.key);
                if (item.key !== "multimodal" && window.location.pathname.startsWith("/chat")) {
                  window.history.pushState(null, "", "/");
                }
              }}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-panel">
        {page === "home" && (
          <ProtectedRoute>
            <Home onStart={() => setPage("checkin")} />
          </ProtectedRoute>
        )}
        {page === "checkin" && (
          <ProtectedRoute>
            <CheckInPage
              checkin={checkin}
              onChange={setCheckin}
              onNext={() => setPage("multimodal")}
            />
          </ProtectedRoute>
        )}
        {page === "multimodal" && (
          <PermissionRoute permission={Permission.MULTIMODAL_USE}>
            <MultimodalChat checkin={checkin} />
          </PermissionRoute>
        )}
        {page === "relaxation" && (
          <ProtectedRoute>
            <Relaxation />
          </ProtectedRoute>
        )}
        {page === "report" && (
          <PermissionRoute permission={Permission.CONVERSATION_READ_OWN}>
            <Report />
          </PermissionRoute>
        )}
        {page === "video" && (
          <PermissionRoute permission={Permission.MULTIMODAL_USE}>
            <VideoCompanion />
          </PermissionRoute>
        )}
        {page === "knowledge" && (
          <PermissionRoute permission={Permission.KNOWLEDGE_REVIEW}>
            <KnowledgeReview />
          </PermissionRoute>
        )}
        {page === "humanEvaluation" && (
          <PermissionRoute permission={Permission.EVALUATION_REVIEW}>
            <HumanEvaluationReview />
          </PermissionRoute>
        )}
        {page === "evaluation" && (
          <PermissionRoute permission={Permission.EVALUATION_RUN_CREATE}>
            <EvaluationDashboard />
          </PermissionRoute>
        )}
        {page === "developer" && (
          <PermissionRoute permission={Permission.RAG_DEBUG_VIEW}>
            <DeveloperDashboard onOpenEvaluation={() => setPage("evaluation")} />
          </PermissionRoute>
        )}
        {page === "admin" && (
          <PermissionRoute permission={Permission.USER_MANAGE}>
            <AdminDashboard />
          </PermissionRoute>
        )}
        {!visibleNavItems.some((item) => item.key === page) && <AccessDenied />}
      </main>
    </div>
  );
}
