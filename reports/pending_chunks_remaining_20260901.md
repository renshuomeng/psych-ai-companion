# CARE-Psy Remaining Pending Chunks 2026-09-01

- Pending chunks: 1648
- CSV: `reports/pending_chunks_remaining_20260901.csv`

## By Collection

| Item | Count |
|---|---:|
| `helping_skills` | 682 |
| `interventions` | 634 |
| `professional_knowledge` | 184 |
| `safety` | 148 |

## By Use Mode

| Item | Count |
|---|---:|
| `helping_skills_only` | 682 |
| `direct_user_support` | 634 |
| `psychoeducation_only` | 184 |
| `safety_only` | 148 |

## By Risk Scope

| Item | Count |
|---|---:|
| `normal` | 1500 |
| `safety_route_only` | 148 |

## By Language

| Item | Count |
|---|---:|
| `en` | 1646 |
| `zh-CN` | 2 |

## By Chunk Type

| Item | Count |
|---|---:|
| `psychoeducation` | 714 |
| `helping_skill` | 682 |
| `safety_guidance` | 148 |
| `exercise` | 76 |
| `communication_skill` | 24 |
| `intervention_step` | 4 |

## Top Sources

| Item | Count |
|---|---:|
| `WHO_EASE_INTERVENTION_2023` | 585 |
| `WHO_EASE_TRAINING_2025` | 449 |
| `CCI_DISORDERED_EATING` | 167 |
| `NICE_SELF_HARM` | 145 |
| `WHO_PM_PLUS_TRAINING_2025` | 74 |
| `WHO_GROUP_PM_PLUS_TRAINING_2026` | 64 |
| `WHO_HELPING_SKILLS_2025` | 48 |
| `VA_SKILLS_PSYCHOLOGICAL_RECOVERY` | 46 |
| `WHO_SELFHELP_2026` | 26 |
| `WHO_GROUP_PM_PLUS_2020` | 22 |
| `NIMH_EATING_DISORDERS` | 11 |
| `CCI_BODY_DYSMORPHIA` | 2 |
| `NIMH_AUTISM` | 2 |
| `NIMH_SUICIDE_PREVENTION` | 2 |
| `CCI_BIPOLAR` | 1 |
| `CCI_SELF_ESTEEM` | 1 |
| `WHO_PFA_FACILITATOR_2013` | 1 |
| `WHO_SAFETY_PLANNING_2023` | 1 |
| `WHO_THINKING_HEALTHY_2015` | 1 |

## 建议处理

- `safety_only` / `safety_route_only`：只允许安全专项复核后进入 SafetyAgent 专用路线，不能进入普通聊天 RAG。
- `clinical_reference_only`：默认不进入普通用户回答；如果要使用，应由专业人员审核并保持 clinical-only route。
- `helping_skills_only`：适合训练/约束助手行为，不适合原样作为用户 citation；可保留 pending 或转入 agent policy。
- 普通 `direct_user_support`：可以继续按 source 审核，批准后重建 production。
