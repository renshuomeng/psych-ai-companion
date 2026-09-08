# soulchat SFT Selection Report

## Summary

- Raw file: `C:\Users\renshuomeng\Downloads\SoulChatCorpus-sft-multi-Turn.json`
- Raw records: 258353
- Normalized records: 258353
- Rejected records: 13124
- In-dataset duplicates: 147995
- Cross-dataset duplicates against earlier selected sets: 0
- Scored eligible records: 97454
- Candidate records: 980
- Final selected records: 600
- Average final score: 89.88

## Length Distribution After Hard Filters

```json
{
  "turn_count": {
    "p1": 2.0,
    "p5": 8.0,
    "p50": 12.0,
    "p90": 14.0,
    "p95": 16.0,
    "p99": 18.0
  },
  "characters": {
    "p1": 342.0,
    "p5": 428.0,
    "p50": 736.0,
    "p90": 1137.0,
    "p95": 1279.0,
    "p99": 1574.0
  },
  "estimated_tokens": {
    "p1": 230.0,
    "p5": 289.0,
    "p50": 503.0,
    "p90": 781.0,
    "p95": 879.0,
    "p99": 1083.0
  }
}
```

## Reject Reasons

- high_risk_without_safety_response: 11881
- unsafe_boundary_medication_directive: 561
- post_candidate_high_risk_not_immediate_safe: 220
- unsafe_boundary_recovery_guarantee: 210
- too_short_for_sft: 82
- broken_conversation: 78
- unsafe_boundary_direct_diagnosis: 64
- low_information: 17
- unsafe_boundary_professional_only_procedure: 4
- assistant_too_short: 4
- unsafe_boundary_medication_directive|recovery_guarantee: 2
- unsafe_boundary_medication_directive|direct_diagnosis: 1

## Final Distribution

### Group

### group

- 通用人群: 600

### problem

- 治疗: 81
- 心理学知识: 74
- 社会: 65
- 行为: 57
- 情绪: 56
- 家庭: 54
- 职场: 54
- 婚恋: 45
- 人际: 35
- 成长: 26
- 自我: 24
- 未明确: 22
- 性心理: 7

### cause

- unknown_cause: 600

### support_focus

- 安全支持、情绪命名、行动计划: 85
- 安全支持、认知重评、情绪命名: 83
- 情绪命名、行动计划、自我接纳: 56
- 情绪命名、行动计划: 55
- 认知重评、情绪命名、自我接纳: 37
- 认知重评、情绪命名: 32
- 情绪命名、社会支持、自我接纳: 29
- 情绪命名、行动计划、社会支持: 27
- 认知重评、情绪命名、社会支持: 24
- 情绪命名、社会支持: 24
- 认知重评、行动计划、社会支持: 21
- 情绪命名: 16
- 情绪命名、自我接纳: 12
- 安全支持、情绪命名、社会支持: 10
- 认知重评、情绪命名、行动计划: 10
- 认知重评、行动计划、自我接纳: 9
- 安全支持、情绪命名: 8
- 认知重评、行动计划: 7
- 认知重评、社会支持: 4
- 安全支持: 4
- 安全支持、自我接纳: 4
- 安全支持、认知重评: 3
- 认知重评: 3
- 安全支持、认知重评、行动计划: 3
- 行动计划、社会支持、自我接纳: 3
- 认知重评、社会支持、自我接纳: 3
- 安全支持、行动计划: 3
- 安全支持、社会支持: 3
- 安全支持、情绪命名、自我接纳: 2
- 安全支持、行动计划、社会支持: 2

### strategy

- emotion_labeling: 500
- resource_referral: 399
- grounding_relaxation: 388
- safety_planning: 340
- problem_solving: 325
- psychoeducation: 325
- empathy_validation: 308
- open_question: 288
- cognitive_reframe: 284
- supportive_dialogue: 5

### severity

- medium: 274
- low: 254
- high: 72

## Final Length Stats

- Selected estimated-token percentiles: `{"p1":300.0,"p5":327.0,"p50":514.0,"p90":752.1,"p95":810.05,"p99":862.01}`
- Selected turn-count percentiles: `{"p1":8.0,"p5":8.0,"p50":12.0,"p90":14.0,"p95":16.0,"p99":20.0}`

## Output Files

- normalized_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\normalized\soulchat_normalized.jsonl`
- selected_json: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_selected_600.json`
- selected_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_selected_600.jsonl`
- ark_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_selected_600_ark.jsonl`
- candidate_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_candidate_1200.jsonl`
- refined_candidate_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_candidate_refined_980.jsonl`
- manifest_csv: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_selection_manifest.csv`
- duplicate_clusters_csv: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_duplicate_clusters.csv`
- manual_review_100_jsonl: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\soulchat_manual_review_100.jsonl`
- schema_report_json: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\soulchat_schema_report.json`

## Notes

- The source files were read only and were not modified.
- Ark JSONL contains only `messages`; metadata stays in the selected JSON/JSONL and manifest.
- Token counts are local estimates because no tokenizer dependency is required for this data-preparation step.
- No paid LLM review or rewriting was performed.

## Post-candidate Safety Refinement

- Original candidate records: 1200
- Refined candidate records: 980
- Excluded high-risk records without immediate safety response: 220
- High severity cap in final selection: <= 12%
