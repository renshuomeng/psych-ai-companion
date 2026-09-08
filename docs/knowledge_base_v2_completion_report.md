# CARE-Psy Knowledge Base V2 Completion Report

## A. Current vs V2
- Knowledge base version: V2
- Sources: 67
- Chunks: 13127
- Approved chunks: 0

## B. Sources
- Candidates selected/generated: 49
- Manual review candidates: 0
- Download failures: 3

## C. Organizations
- Centre for Clinical Interventions, Government of Western Australia: 16
- NHS / Every Mind Matters: 6
- National Institute for Health and Care Excellence: 3
- National Institute of Mental Health: 9
- National Institute on Aging: 2
- Substance Abuse and Mental Health Services Administration: 2
- UNICEF: 2
- VA National Center for PTSD: 1
- World Health Organization: 16
- World Health Organization / International Labour Organization: 1
- World Health Organization / UNICEF: 3
- 中华人民共和国教育部: 3
- 中华人民共和国教育部等十七部门: 2
- 国家卫生健康委员会: 1

## D. Population Coverage
- children: Strong
- adolescents: Strong
- young_adults: Strong
- adults: Strong
- middle_aged: Missing
- older_adults: Strong
- students: Missing
- university_students: Strong
- workers: Strong
- job_seekers: Missing
- parents: Strong
- caregivers: Strong
- pregnant_people: Adequate
- postpartum_people: Adequate
- people_experiencing_grief: Missing
- people_exposed_to_trauma: Strong
- people_with_chronic_illness: Missing
- family_members_supporting_others: Strong

## E. Topic Coverage
- stress: Strong
- anxiety: Strong
- low_mood: Strong
- depressive_feelings: Adequate
- worry: Strong
- rumination: Weak
- panic: Strong
- sleep: Strong
- insomnia: Weak
- loneliness: Missing
- social_isolation: Missing
- anger: Missing
- frustration: Missing
- shame: Weak
- guilt: Missing
- grief: Missing
- bereavement: Missing
- self_criticism: Adequate
- self_compassion: Strong
- self_esteem: Weak
- perfectionism: Weak
- procrastination: Adequate
- avoidance: Strong
- motivation: Weak
- decision_making: Missing
- problem_solving: Strong
- emotion_regulation: Strong
- distress_tolerance: Weak
- friendship: Missing
- social_relationships: Missing
- romantic_relationships: Missing
- marriage: Missing
- family_relationships: Missing
- parent_child_relationship: Weak
- roommate_conflict: Missing
- communication: Strong
- assertiveness: Weak
- conflict_management: Weak
- breakup: Missing
- divorce: Missing
- caregiving_stress: Adequate
- academic_pressure: Missing
- exam_stress: Missing
- thesis_pressure: Missing
- research_failure: Missing
- career_uncertainty: Missing
- employment_anxiety: Missing
- job_search: Missing
- work_stress: Missing
- burnout_related_distress: Missing
- workplace_relationship: Missing
- return_to_work: Missing
- retirement_transition: Missing
- depression: Strong
- anxiety_disorders: Strong
- social_anxiety: Adequate
- OCD: Weak
- BDD: Weak
- PTSD: Weak
- eating_disorders: Adequate
- bipolar_disorder: Strong
- psychosis: Missing
- ADHD: Weak
- autism: Weak
- dementia: Adequate
- substance_use: Missing

## F. Languages
- en: 12088
- zh-CN: 1039

## G. Collections
- campus_support: 36
- evidence: 971
- governance: 268
- helping_skills: 2500
- interventions: 6909
- professional_knowledge: 1626
- safety: 817

## H. Use Modes
- agent_policy_only: 304
- clinical_reference_only: 968
- direct_user_support: 6954
- evidence_only: 3
- helping_skills_only: 2500
- psychoeducation_only: 1581
- safety_only: 817

## I. Deduplication
- Exact duplicate groups sampled: 50
- CCI/NHS overlap is controlled at source-selection level; newly generated registry caps assets per source.

## J. Chunk Quality
- Mean/median/p95 chars: 541.16 / 508 / 886
- Quality issue sample count: 200
- Unsafe excluded chunks: 0

## K. Retrieval
- BM25 staging documents: 13127
- BM25 production documents: 0
- Chroma collections: {"psych_professional_knowledge_staging": 465, "psych_interventions_staging": 559, "psych_campus_support_staging": 0, "psych_governance_staging": 0, "psych_safety_staging": 0, "psych_evidence_staging": 0, "psych_helping_skills_staging": 0}
- Benchmark summary: {"bm25_hit": 0.125, "dense_hit": 0.5, "hybrid_hit": 0.5, "bm25_mrr": 0.0917, "dense_mrr": 0.4417, "hybrid_mrr": 0.4625, "bm25_ndcg": 0.1, "dense_ndcg": 0.4473, "hybrid_ndcg": 0.4732, "bm25_no_result": 0.0, "dense_no_result": 0.0, "hybrid_no_result": 0.0, "hybrid_wrong_population_rate": 0.0, "hybrid_wrong_use_mode_rate": 0.0, "hybrid_safety_leakage_rate": 0.0, "hybrid_duplicate_rate": 0.06, "hybrid_language_preference_accuracy": 0.0, "hybrid_insufficient_evidence_rate": 0.0}

## L. Safety Isolation
- Ordinary RAG filter excludes safety_only, clinical_reference_only, evidence_only, agent_policy_only and helping_skills_only unless an explicit safety/psychoeducation route requests them.
- Safety collection ordinary access: NO.

## M. Cross Language
- Retrieval keeps bilingual query expansion and adds Chinese-source preference for Chinese queries.

## N. Missing Areas
- Missing topics by indexed chunks: loneliness, social_isolation, anger, frustration, guilt, grief, bereavement, decision_making, friendship, social_relationships, romantic_relationships, marriage, family_relationships, roommate_conflict, breakup, divorce, academic_pressure, exam_stress, thesis_pressure, research_failure, career_uncertainty, employment_anxiety, job_search, work_stress, burnout_related_distress, workplace_relationship, return_to_work, retirement_transition, psychosis, substance_use
- Weak/missing populations by indexed chunks: middle_aged, students, job_seekers, people_experiencing_grief, people_with_chronic_illness

## O. Manual Acquisition
- Manual acquisition candidates: C:/Users/renshuomeng/Documents/Codex/2026-06-30/ban/psych-ai-companion/backend/data/knowledge_base/reports/manual_acquisition_candidates.csv
- Automatic download limitations observed:
  - NIA older-adult loneliness/depression pages returned HTTP 405 in this environment; keep as registry candidates and manually confirm/download official assets later.
  - SAMHSA family support and trauma-informed pages returned HTTP 403; do not bypass access controls, use manual official downloads if needed.
  - UNICEF adolescent mental health returned HTTP 403; UNICEF parenting page downloaded successfully.
  - Duplicate CN_MOE aliases failed with connection reset, while the existing MOE registry IDs downloaded successfully.
  - NIMH eating-disorders and suicide-prevention pages downloaded the core source page, but one linked publications asset hit a Windows path issue; source content remains partially available.

## P. Final Status
- STAGING_READY=True
- PRODUCTION_READY=False
- Production remains false until human review approves chunks and production index is built.
