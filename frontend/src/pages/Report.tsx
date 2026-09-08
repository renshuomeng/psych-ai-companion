import { useEffect, useState } from "react";

import { getReport, type ReportResponse } from "../api/client";

export default function Report() {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState("");
  const hasItems = Boolean(report?.items.length);

  useEffect(() => {
    getReport()
      .then(setReport)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "报告数据加载失败"),
      );
  }, []);

  return (
    <section className="page-stack">
      <div className="section-heading">
        <span className="eyebrow">Report</span>
        <h1>趋势报告</h1>
        <p>这里展示用户完成自助练习后提交的真实反馈；没有提交反馈时不会用模拟数据填充。</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <section className="report-panel">
        <h2>{report?.summary ?? "正在加载报告..."}</h2>
        {hasItems ? (
          <div className="bar-chart" aria-label="最近 7 次压力评分">
            {report?.items.map((item) => (
              <div className="bar-item" key={item.date}>
                <div className="bar-track">
                  <span style={{ height: `${item.stress_score * 10}%` }} />
                </div>
                <strong>{item.stress_score}</strong>
                <span>{item.date}</span>
                <small>{item.emotion}</small>
              </div>
            ))}
          </div>
        ) : (
          <div className="placeholder-panel">
            <strong>还没有可展示的真实反馈记录</strong>
            <p>完成自助练习并提交前后压力评分后，趋势报告才会生成柱状图。</p>
          </div>
        )}
      </section>
    </section>
  );
}
