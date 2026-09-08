# cpsdd SFT Selection Report

## Summary

- Raw file: `C:\Users\renshuomeng\Downloads\train.json`
- Raw records: 54508
- Normalized records: 54508
- Rejected records: 1651
- In-dataset duplicates: 20015
- Cross-dataset duplicates against earlier selected sets: 0
- Scored eligible records: 32905
- Candidate records: 1937
- Final selected records: 1000
- Average final score: 91.742

## Length Distribution After Hard Filters

```json
{
  "turn_count": {
    "p1": 6.0,
    "p5": 8.0,
    "p50": 16.0,
    "p90": 20.0,
    "p95": 22.0,
    "p99": 26.0
  },
  "characters": {
    "p1": 504.0,
    "p5": 607.0,
    "p50": 1084.0,
    "p90": 1669.0,
    "p95": 1897.0,
    "p99": 2455.0
  },
  "estimated_tokens": {
    "p1": 331.19,
    "p5": 402.0,
    "p50": 724.0,
    "p90": 1113.0,
    "p95": 1267.0,
    "p99": 1637.81
  }
}
```

## Reject Reasons

- high_risk_without_safety_response: 1527
- post_candidate_high_risk_not_immediate_safe: 63
- unsafe_boundary_medication_directive: 32
- unsafe_boundary_recovery_guarantee: 27
- unsafe_boundary_direct_diagnosis: 2

## Final Distribution

### Group

### group

- 后续照管: 131
- 精神病人: 108
- 大学生: 106
- 戒毒人员: 102
- 服刑人员: 101
- 残障人士: 91
- 家长群体: 87
- 癌症患者: 83
- 中学生: 82
- 孤儿: 55
- 中老年群体: 28
- 小学生: 18
- 幼儿群体: 8

### problem

- 敌对: 5
- 孤独、躺平: 4
- 自杀: 4
- 自杀、自卑: 4
- 躺平、自卑: 4
- 敌对、偏执: 4
- 成瘾、敌对、自卑: 3
- 自卑、偏执: 3
- 焦虑、自杀、自残: 3
- 社恐、空心: 3
- 自杀、敌对: 3
- 偏执、抑郁、空心: 3
- 敌对、强迫、躺平: 3
- 恋爱、自卑: 3
- 孤独、自杀: 3
- 敌对、孤独: 3
- 孤独、成瘾、自卑: 3
- 躺平、恋爱: 3
- 自卑、焦虑、敌对: 3
- 强迫、社恐: 3
- 自卑、空心、恋爱: 3
- 躺平、抑郁: 3
- 社恐、躺平: 3
- 躺平、孤独: 3
- 社恐、抑郁: 3
- 自杀、偏执: 3
- 抑郁、偏执、敌对: 3
- 成瘾、LGBT、抑郁: 3
- 空心、社恐、敌对: 3
- 自卑、偏执、成瘾: 3

### cause

- 失恋、失业破产: 5
- 考试失败: 5
- 霸凌: 4
- 性侵: 4
- 工作压力、考试失败: 4
- 霸凌、失恋: 4
- 婚变、工作压力、失恋: 4
- 霸凌、童年创伤: 4
- 失业破产、社会支持: 4
- 性侵、婚变: 4
- 性侵、霸凌: 4
- 性侵、学业压力、亲人去世: 3
- 童年创伤、婚变、亲人去世: 3
- 霸凌、婚变、亲人去世: 3
- 婚变、社会支持: 3
- 社交压力、家庭关系、婚变: 3
- 考试失败、学业压力、童年创伤: 3
- 社会支持、失业破产: 3
- 工作压力、童年创伤: 3
- 失业破产、考试失败: 3
- 失业破产、失恋: 3
- 社交压力、家庭关系、失业破产: 3
- 考试失败、亲人去世、婚变: 3
- 霸凌、社会支持、社交压力: 3
- 家庭关系、工作压力、考试失败: 3
- 工作压力、社会支持、家庭关系: 3
- 霸凌、学业压力、家庭关系: 3
- 社交压力、失恋: 3
- 婚变、亲人去世: 3
- 失恋、社会支持、考试失败: 3

### support_focus

- 婚姻关系、创新思维: 6
- 婚姻关系、学习能力: 6
- 学习能力、婚姻关系: 6
- 婚姻关系: 6
- 归属感、内驱力: 5
- 恋爱择偶: 5
- 创新思维、学习能力: 5
- 婚姻关系、归属感: 5
- 逻辑思维、恋爱择偶: 5
- 松弛感、链接能力: 4
- 松弛感、力量感: 4
- 归属感、逻辑思维: 4
- 恋爱择偶、链接能力: 4
- 力量感、创新思维: 4
- 链接能力、内驱力: 4
- 创新思维、逻辑思维: 4
- 归属感、婚姻关系: 4
- 松弛感、归属感: 4
- 逻辑思维、亲子关系: 4
- 松弛感、婚姻关系: 4
- 逻辑思维、松弛感: 4
- 逻辑思维、松弛感、亲子关系: 3
- 亲子关系、婚姻关系、安全感: 3
- 亲子关系、归属感、创新思维: 3
- 安全感、恋爱择偶、内驱力: 3
- 力量感、亲子关系、安全感: 3
- 归属感、链接能力、学习能力: 3
- 学习能力、归属感、恋爱择偶: 3
- 内驱力、松弛感、链接能力: 3
- 恋爱择偶、创新思维、链接能力: 3

### strategy

- 先问候语: 1000
- 安慰鼓励: 1000
- 引导提问: 981
- emotion_labeling: 959
- 结尾语言: 916
- 推荐音乐: 851
- 推荐电影: 831
- grounding_relaxation: 712
- 推荐书方: 706
- cognitive_reframe: 572
- 建议方法: 552
- 其他推荐: 459
- empathy_validation: 415
- open_question: 388
- psychoeducation: 374
- problem_solving: 290
- resource_referral: 237
- safety_planning: 221

### severity

- medium: 556
- low: 438
- high: 6

## Final Length Stats

- Selected estimated-token percentiles: `{"p1":441.97,"p5":521.95,"p50":764.5,"p90":1037.1,"p95":1139.0,"p99":1230.06}`
- Selected turn-count percentiles: `{"p1":6.0,"p5":8.0,"p50":14.0,"p90":20.0,"p95":22.0,"p99":24.0}`

## Output Files

- normalized_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\normalized\cpsdd_normalized.jsonl`
- selected_json: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_selected_1000.json`
- selected_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_selected_1000.jsonl`
- ark_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_selected_1000_ark.jsonl`
- candidate_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_candidate_2000.jsonl`
- refined_candidate_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_candidate_refined_1937.jsonl`
- manifest_csv: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_selection_manifest.csv`
- duplicate_clusters_csv: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_duplicate_clusters.csv`
- manual_review_100_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\cpsdd_manual_review_100.jsonl`
- schema_report_json: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\cpsdd_schema_report.json`

## Notes

- The source files were read only and were not modified.
- Ark JSONL contains only `messages`; metadata stays in the selected JSON/JSONL and manifest.
- Token counts are local estimates because no tokenizer dependency is required for this data-preparation step.
- No paid LLM review or rewriting was performed.

## Post-candidate Safety Refinement

- Original candidate records: 2000
- Refined candidate records: 1937
- Excluded high-risk records without immediate safety response: 63
- High severity cap in final selection: <= 12%
