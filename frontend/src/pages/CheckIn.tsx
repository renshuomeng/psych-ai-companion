import type { CheckIn } from "../api/client";

type CheckInProps = {
  checkin: CheckIn;
  onChange: (checkin: CheckIn) => void;
  onNext: () => void;
};

const SOURCE_OPTIONS = [
  "论文",
  "考试",
  "就业",
  "人际关系",
  "睡眠",
  "孤独感",
  "家庭",
  "经济",
];

const STYLE_OPTIONS = ["温和陪伴", "理性分析", "行动建议"];

export default function CheckInPage({ checkin, onChange, onNext }: CheckInProps) {
  function toggleSource(source: string) {
    const hasSource = checkin.stress_source.includes(source);
    const stress_source = hasSource
      ? checkin.stress_source.filter((item) => item !== source)
      : [...checkin.stress_source, source];

    onChange({ ...checkin, stress_source });
  }

  return (
    <section className="page-stack">
      <div className="section-heading">
        <span className="eyebrow">Check In</span>
        <h1>情绪打卡</h1>
        <p>这些信息只保存在浏览器本地，用来帮助 Chat 页面生成更贴近当前状态的回复。</p>
      </div>

      <section className="form-panel">
        <label className="field-label" htmlFor="stress-score">
          当前压力评分：{checkin.stress_score}/10
        </label>
        <input
          id="stress-score"
          max={10}
          min={0}
          onChange={(event) =>
            onChange({ ...checkin, stress_score: Number(event.target.value) })
          }
          type="range"
          value={checkin.stress_score}
        />

        <div>
          <span className="field-label">压力来源</span>
          <div className="option-grid">
            {SOURCE_OPTIONS.map((source) => (
              <label className="check-option" key={source}>
                <input
                  checked={checkin.stress_source.includes(source)}
                  onChange={() => toggleSource(source)}
                  type="checkbox"
                />
                {source}
              </label>
            ))}
          </div>
        </div>

        <label className="field-label" htmlFor="preferred-style">
          倾诉偏好
        </label>
        <select
          id="preferred-style"
          onChange={(event) =>
            onChange({ ...checkin, preferred_style: event.target.value })
          }
          value={checkin.preferred_style}
        >
          {STYLE_OPTIONS.map((style) => (
            <option key={style} value={style}>
              {style}
            </option>
          ))}
        </select>

        <div className="form-actions">
          <span className="save-state">已自动保存到 localStorage</span>
          <button className="primary-button" onClick={onNext} type="button">
            去文字陪伴
          </button>
        </div>
      </section>
    </section>
  );
}
