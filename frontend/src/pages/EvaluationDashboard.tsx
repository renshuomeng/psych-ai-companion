import { useEffect, useMemo, useState } from "react";

import {
  compareEvaluationRuns,
  getEvaluationRegistry,
  getEvaluationRun,
  importKnowledge,
  listEvaluationRuns,
  runEvaluation,
  type EvaluationAblation,
  type EvaluationCompareResponse,
  type EvaluationRegistryResponse,
  type EvaluationRunDetailResponse,
  type EvaluationRunSummary,
} from "../api/client";

const DEFAULT_FRAMEWORKS = ["care_bench", "esc_eval", "cpsycoun", "counselbench"];
const DEFAULT_ABLATION: EvaluationAblation = {
  risk: true,
  psychological_state: true,
  strategy: true,
  rag: true,
  safety: true,
};

function statusText(value: string) {
  if (value === "Compatible") return "兼容烟测";
  if (value === "Partial") return "部分接入";
  if (value === "Unavailable") return "官方未接入";
  return value;
}

function directionText(value: string) {
  return value === "lower_is_better" ? "越低越好" : "越高越好";
}

export default function EvaluationDashboard() {
  const [registry, setRegistry] = useState<EvaluationRegistryResponse | null>(null);
  const [systemId, setSystemId] = useState("full_agent");
  const [frameworks, setFrameworks] = useState(DEFAULT_FRAMEWORKS);
  const [limit, setLimit] = useState(5);
  const [dryRun, setDryRun] = useState(false);
  const [useCache, setUseCache] = useState(true);
  const [ablation, setAblation] = useState<EvaluationAblation>(DEFAULT_ABLATION);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [summary, setSummary] = useState<EvaluationRunSummary | null>(null);
  const [detail, setDetail] = useState<EvaluationRunDetailResponse | null>(null);
  const [runs, setRuns] = useState<EvaluationRunSummary[]>([]);
  const [baselineRunId, setBaselineRunId] = useState("");
  const [candidateRunId, setCandidateRunId] = useState("");
  const [comparison, setComparison] = useState<EvaluationCompareResponse | null>(null);

  const selectedSystem = registry?.systems[systemId];
  const effectiveAblation = useMemo(() => {
    if (systemId === "agent_without_rag") return { ...DEFAULT_ABLATION, rag: false };
    if (systemId === "agent_without_strategy") return { ...DEFAULT_ABLATION, strategy: false };
    if (systemId === "agent_without_psychological_state") return { ...DEFAULT_ABLATION, psychological_state: false };
    if (systemId === "direct_doubao") {
      return { risk: false, psychological_state: false, strategy: false, rag: false, safety: false };
    }
    if (systemId === "custom_agent") return ablation;
    return DEFAULT_ABLATION;
  }, [ablation, systemId]);

  async function refreshRuns() {
    const response = await listEvaluationRuns();
    const saved = response.saved_runs || [];
    setRuns(saved);
    if (!baselineRunId && saved[1]) setBaselineRunId(saved[1].run_id);
    if (!candidateRunId && saved[0]) setCandidateRunId(saved[0].run_id);
  }

  useEffect(() => {
    void getEvaluationRegistry()
      .then(setRegistry)
      .catch((err) => setMessage(err instanceof Error ? err.message : "读取评价注册表失败。"));
    void refreshRuns().catch(() => undefined);
  }, []);

  async function runKnowledgeImport() {
    setLoading(true);
    setMessage("");
    try {
      const result = await importKnowledge();
      setMessage(`知识库构建完成：${JSON.stringify(result)}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "知识库构建失败。");
    } finally {
      setLoading(false);
    }
  }

  async function runCenterEvaluation() {
    setLoading(true);
    setMessage("");
    setComparison(null);
    setDetail(null);
    try {
      const result = await runEvaluation({
        system_id: systemId,
        frameworks,
        limit,
        dry_run: dryRun,
        ablation: effectiveAblation,
        use_cache: useCache,
      });
      setSummary(result);
      const runDetail = await getEvaluationRun(result.run_id);
      setDetail(runDetail);
      await refreshRuns();
      setMessage(`评测完成：${result.run_id}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "评测运行失败。");
    } finally {
      setLoading(false);
    }
  }

  async function runComparison() {
    if (!baselineRunId || !candidateRunId) return;
    setLoading(true);
    setMessage("");
    try {
      const result = await compareEvaluationRuns({
        baseline_run_id: baselineRunId,
        candidate_run_id: candidateRunId,
      });
      setComparison(result);
      setMessage(`对比完成，CSV：${result.export_csv}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "对比失败。");
    } finally {
      setLoading(false);
    }
  }

  function toggleFramework(id: string) {
    setFrameworks((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function toggleAblation(key: keyof EvaluationAblation) {
    setAblation((current) => ({ ...current, [key]: !current[key] }));
  }

  const displayedCaseScores = detail?.case_scores?.slice(0, 4) || [];

  return (
    <section className="page-stack evaluation-page">
      <div className="section-heading wide-heading">
        <span className="eyebrow">Evaluation Center</span>
        <h1>CARE-Psy Evaluation Center</h1>
        <p>
          面向竞赛答辩的系统级指标评价：候选系统、消融配置、心理咨询评价框架、case 级输出和 trace 分离保存。
          默认只运行烟测样本，避免误触发大规模付费评测。
        </p>
      </div>

      {message && <div className={message.includes("失败") ? "error-banner" : "notice-band"}>{message}</div>}

      <section className="evaluation-layout">
        <div className="evaluation-controls">
          <section className="result-card">
            <div className="panel-title-row">
              <div>
                <h2>系统配置</h2>
                <p>选择要评价的候选系统，完整 Agent 会调用现有多 Agent 链路。</p>
              </div>
              <button disabled={loading} onClick={runKnowledgeImport} type="button">
                构建知识库
              </button>
            </div>
            <div className="radio-stack">
              {registry &&
                Object.entries(registry.systems).map(([id, item]) => (
                  <label className={systemId === id ? "choice-row active" : "choice-row"} key={id}>
                    <input checked={systemId === id} onChange={() => setSystemId(id)} type="radio" />
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.description}</small>
                    </span>
                  </label>
                ))}
            </div>
          </section>

          <section className="result-card">
            <h2>评价框架</h2>
            <div className="framework-grid">
              {registry &&
                Object.entries(registry.frameworks).map(([id, item]) => (
                  <label className={frameworks.includes(id) ? "choice-row active" : "choice-row"} key={id}>
                    <input checked={frameworks.includes(id)} onChange={() => toggleFramework(id)} type="checkbox" />
                    <span>
                      <strong>{item.name}</strong>
                      <small>{statusText(item.local_status)} / 官方状态：{statusText(item.official_status)}</small>
                    </span>
                  </label>
                ))}
            </div>
          </section>

          <section className="result-card">
            <h2>运行参数</h2>
            <div className="settings-grid">
              <label>
                <span>样本数</span>
                <input
                  max={registry?.limits.smoke_case_limit || 10}
                  min={1}
                  onChange={(event) => setLimit(Number(event.target.value))}
                  type="number"
                  value={limit}
                />
              </label>
              <label className="switch-row">
                <input checked={dryRun} onChange={() => setDryRun((value) => !value)} type="checkbox" />
                <span>Dry run</span>
              </label>
              <label className="switch-row">
                <input checked={useCache} onChange={() => setUseCache((value) => !value)} type="checkbox" />
                <span>使用缓存</span>
              </label>
            </div>
            <div className="ablation-grid">
              {Object.entries(effectiveAblation).map(([key, value]) => (
                <label className="switch-row" key={key}>
                  <input
                    checked={value}
                    disabled={systemId !== "custom_agent"}
                    onChange={() => toggleAblation(key as keyof EvaluationAblation)}
                    type="checkbox"
                  />
                  <span>{key}</span>
                </label>
              ))}
            </div>
            <button className="primary-button" disabled={loading || frameworks.length === 0} onClick={runCenterEvaluation} type="button">
              {loading ? "运行中..." : "Run Evaluation"}
            </button>
          </section>
        </div>

        <div className="evaluation-results">
          <section className="result-card">
            <h2>系统统计</h2>
            <div className="metrics-grid">
              <div>
                <span>候选系统</span>
                <strong>{summary?.system_name || selectedSystem?.name || "未运行"}</strong>
              </div>
              <div>
                <span>Case 数</span>
                <strong>{summary?.case_count ?? 0}</strong>
              </div>
              <div>
                <span>平均延迟</span>
                <strong>{summary?.system_statistics?.mean_latency_ms ?? 0} ms</strong>
              </div>
              <div>
                <span>引用知识库</span>
                <strong>{summary?.system_statistics?.knowledge_source_cases ?? 0}</strong>
              </div>
              <div>
                <span>高风险</span>
                <strong>{summary?.system_statistics?.high_risk_cases ?? 0}</strong>
              </div>
              <div>
                <span>错误数</span>
                <strong>{summary?.system_statistics?.error_count ?? 0}</strong>
              </div>
            </div>
          </section>

          <section className="result-card">
            <h2>框架指标</h2>
            {summary ? (
              <div className="framework-results">
                {Object.entries(summary.frameworks || {}).map(([frameworkId, framework]) => (
                  <div className="metric-table" key={frameworkId}>
                    <div className="metric-table-heading">
                      <strong>{framework.name}</strong>
                      <span>{statusText(framework.local_status)} / 官方：{statusText(framework.official_status)}</span>
                    </div>
                    {Object.entries(framework.metrics).map(([metricName, metric]) => (
                      <div className="metric-table-row" key={metricName}>
                        <span>{metricName}</span>
                        <strong>{metric.mean}</strong>
                        <small>{directionText(metric.direction)} · n={metric.n}</small>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <p>运行评测后会按 CARE-Bench、ESC-Eval、CPsyCounE、CounselBench 分别展示指标，不计算跨框架总分。</p>
            )}
          </section>

          <section className="result-card">
            <h2>Case 分析</h2>
            {displayedCaseScores.length ? (
              <div className="case-list">
                {displayedCaseScores.map((row) => {
                  const candidate = row.candidate as Record<string, unknown>;
                  const caseInfo = row.case as { case_id?: string; tags?: string[] };
                  return (
                    <article key={String(row.case_id)}>
                      <div>
                        <strong>{caseInfo?.case_id || String(row.case_id)}</strong>
                        <span>{caseInfo?.tags?.join(" / ")}</span>
                      </div>
                      <p>{String(candidate?.response || "").slice(0, 180)}</p>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p>这里会显示前几个 case 的回复、标签和可追踪中间状态。</p>
            )}
          </section>

          <section className="result-card">
            <h2>运行对比</h2>
            <div className="compare-row">
              <select onChange={(event) => setBaselineRunId(event.target.value)} value={baselineRunId}>
                <option value="">Baseline run</option>
                {runs.map((item) => (
                  <option key={`baseline-${item.run_id}`} value={item.run_id}>
                    {item.run_id}
                  </option>
                ))}
              </select>
              <select onChange={(event) => setCandidateRunId(event.target.value)} value={candidateRunId}>
                <option value="">Candidate run</option>
                {runs.map((item) => (
                  <option key={`candidate-${item.run_id}`} value={item.run_id}>
                    {item.run_id}
                  </option>
                ))}
              </select>
              <button disabled={loading || !baselineRunId || !candidateRunId} onClick={runComparison} type="button">
                Compare
              </button>
            </div>
            {comparison && <pre>{JSON.stringify(comparison.metric_delta, null, 2)}</pre>}
          </section>
        </div>
      </section>
    </section>
  );
}
