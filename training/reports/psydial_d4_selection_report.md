# psydial_d4 SFT Selection Report

## Summary

- Raw file: `C:\Users\renshuomeng\Downloads\PsyDial-D4.json`
- Raw records: 2382
- Normalized records: 2382
- Rejected records: 122
- In-dataset duplicates: 927
- Cross-dataset duplicates against earlier selected sets: 0
- Scored eligible records: 1348
- Candidate records: 785
- Final selected records: 400
- Average final score: 83.217

## Length Distribution After Hard Filters

```json
{
  "turn_count": {
    "p1": 24.0,
    "p5": 32.0,
    "p50": 70.0,
    "p90": 118.0,
    "p95": 140.0,
    "p99": 174.0
  },
  "characters": {
    "p1": 970.7,
    "p5": 1281.0,
    "p50": 2388.0,
    "p90": 3772.2,
    "p95": 4328.6,
    "p99": 4993.64
  },
  "estimated_tokens": {
    "p1": 649.22,
    "p5": 865.7,
    "p50": 1612.0,
    "p90": 2537.2,
    "p95": 2901.0,
    "p99": 3364.26
  }
}
```

## Reject Reasons

- high_risk_without_safety_response: 98
- post_candidate_high_risk_not_immediate_safe: 15
- unsafe_boundary_medication_directive: 9

## Final Distribution

### Group

### group

- 通用人群: 400

### problem

- 学习与论文压力: 172
- 就业与未来焦虑: 144
- 人际关系: 77
- 家庭压力: 4
- 自我与控制感: 3

### cause

- unknown_cause: 400

### support_focus

- 认知重评、情绪命名、行动计划: 244
- 安全支持、认知重评、情绪命名: 78
- 情绪命名、行动计划、社会支持: 27
- 认知重评、情绪命名、社会支持: 19
- 情绪命名、社会支持、自我接纳: 6
- 安全支持、情绪命名、行动计划: 5
- 情绪命名、社会支持: 4
- 情绪命名、行动计划、自我接纳: 4
- 认知重评、情绪命名、自我接纳: 3
- 认知重评、情绪命名: 3
- 情绪命名、行动计划: 2
- 安全支持、情绪命名、社会支持: 1
- 安全支持、情绪命名、自我接纳: 1
- 认知重评、行动计划、社会支持: 1
- 行动计划、社会支持: 1
- 情绪命名、自我接纳: 1

### strategy

- emotion_labeling: 398
- empathy_validation: 396
- open_question: 379
- cognitive_reframe: 297
- problem_solving: 210
- grounding_relaxation: 144
- safety_planning: 114
- psychoeducation: 103
- resource_referral: 101

### severity

- medium: 345
- low: 55

## Final Length Stats

- Selected estimated-token percentiles: `{"p1":678.67,"p5":863.8,"p50":1574.5,"p90":2293.5,"p95":2525.35,"p99":2721.2}`
- Selected turn-count percentiles: `{"p1":21.98,"p5":29.9,"p50":62.0,"p90":98.0,"p95":104.1,"p99":120.02}`

## Output Files

- normalized_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\normalized\psydial_d4_normalized.jsonl`
- selected_json: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_selected_400.json`
- selected_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_selected_400.jsonl`
- ark_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_selected_400_ark.jsonl`
- candidate_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_candidate_800.jsonl`
- refined_candidate_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_candidate_refined_785.jsonl`
- manifest_csv: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_selection_manifest.csv`
- duplicate_clusters_csv: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_duplicate_clusters.csv`
- manual_review_100_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\psydial_d4_manual_review_100.jsonl`
- schema_report_json: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\psydial_d4_schema_report.json`

## Notes

- The source files were read only and were not modified.
- Ark JSONL contains only `messages`; metadata stays in the selected JSON/JSONL and manifest.
- Token counts are local estimates because no tokenizer dependency is required for this data-preparation step.
- No paid LLM review or rewriting was performed.

## Post-candidate Safety Refinement

- Original candidate records: 800
- Refined candidate records: 785
- Excluded high-risk records without immediate safety response: 15
- High severity cap in final selection: <= 12%
