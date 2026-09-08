from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
KB_ROOT = ROOT / "backend" / "data" / "knowledge_base"
SOURCES_DIR = KB_ROOT / "sources"
REPORTS_DIR = KB_ROOT / "reports"
V1_REGISTRY = SOURCES_DIR / "knowledge_sources_v1.yaml"
V2_REGISTRY = SOURCES_DIR / "knowledge_sources.yaml"
COVERAGE_MATRIX = SOURCES_DIR / "coverage_matrix.yaml"

VALID_USE_MODES = {
    "direct_user_support",
    "psychoeducation_only",
    "helping_skills_only",
    "agent_policy_only",
    "safety_only",
    "evidence_only",
    "clinical_reference_only",
}

DIRECT_COLLECTIONS = {"interventions", "professional_knowledge", "campus_support"}
SAFETY_TOPICS = {
    "self_harm",
    "suicidal_thoughts",
    "suicidal_plan",
    "harm_to_others",
    "abuse",
    "domestic_violence",
    "acute_crisis",
    "severe_psychosis",
    "mania",
    "severe_eating_disorder_risk",
    "substance_crisis",
    "minor_safeguarding",
    "perinatal_crisis",
}
SENSITIVE_CONDITIONS = {
    "bipolar_disorder",
    "psychosis",
    "eating_disorders",
    "OCD",
    "BDD",
    "PTSD",
    "substance_use",
    "dementia",
}

EVALUATION_SOURCE_IDS = [
    "CARE-Bench",
    "ESC-Eval",
    "CPsyCounE",
    "CounselBench",
    "CPsyCoun Test",
    "CPsyCounD Train",
    "SoulChat",
    "ESConv",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(text: str, prefix: str = "CAND") -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}".upper()


def domains_for(url: str) -> list[str]:
    host = urlparse(url).hostname or ""
    host = host.lower().removeprefix("www.")
    if not host:
        return []
    domains = {host, f"www.{host}"}
    if host == "who.int":
        domains.add("iris.who.int")
        domains.add("tdr.who.int")
    return sorted(domains)


def source_quality_score(candidate: dict[str, Any]) -> tuple[int, dict[str, int], str]:
    authority_scores = {
        "tier_a": 30,
        "tier_b": 22,
        "tier_c": 14,
        "tier_d": 0,
    }
    evidence_scores = {
        "A": 25,
        "B": 18,
        "C": 10,
        "source_unverified": 0,
    }
    authority = authority_scores.get(str(candidate.get("authority_level") or "tier_d"), 0)
    evidence = evidence_scores.get(str(candidate.get("evidence_level") or "source_unverified"), 0)
    relevance = min(20, 8 + 2 * len(candidate.get("topics") or []) + 2 * len(candidate.get("population") or []))
    license_value = str(candidate.get("license") or "").lower()
    legal = 15 if any(term in license_value for term in ["public", "official", "crown", "cc", "government"]) else 7
    year = candidate.get("year")
    try:
        year_int = int(year)
    except Exception:
        year_int = 0
    freshness = 5 if year_int >= 2024 else 4 if year_int >= 2020 else 3 if year_int >= 2015 else 2
    overlap = str(candidate.get("existing_overlap") or "low")
    non_redundancy = {"low": 5, "medium": 3, "high": 1}.get(overlap, 3)
    parts = {
        "authority": authority,
        "evidence": evidence,
        "project_relevance": relevance,
        "legal_usability": legal,
        "freshness": freshness,
        "non_redundancy": non_redundancy,
    }
    total = sum(parts.values())
    if total >= 80:
        decision = "strong_include"
    elif total >= 65:
        decision = "include_if_gap"
    elif total >= 50:
        decision = "manual_review"
    else:
        decision = "reject"
    return total, parts, decision


def c(
    candidate_id: str,
    title: str,
    organization: str,
    official_url: str,
    *,
    year: int | None,
    language: str | list[str],
    source_type: str,
    collection: str,
    use_mode: str,
    topics: list[str],
    population: list[str] | None = None,
    life_stages: list[str] | None = None,
    evidence_level: str = "B",
    authority_level: str = "tier_a",
    license: str = "official_public_source",
    downloadable: bool = True,
    auto_download: bool | None = None,
    existing_overlap: str = "low",
    asset_url: str = "",
    context: str = "",
    notes: str = "",
) -> dict[str, Any]:
    if use_mode not in VALID_USE_MODES:
        raise ValueError(f"Invalid use_mode for {candidate_id}: {use_mode}")
    population = population or ["adults"]
    life_stages = life_stages or []
    topics = topics or []
    risk_scope = "safety_route_only" if use_mode == "safety_only" or collection == "safety" else "normal"
    clinical_only = use_mode in {"clinical_reference_only", "evidence_only"}
    user_facing = use_mode == "direct_user_support" and collection in DIRECT_COLLECTIONS and not clinical_only
    if any(topic in SENSITIVE_CONDITIONS for topic in topics) and use_mode == "direct_user_support":
        use_mode = "psychoeducation_only"
        user_facing = False
    score, parts, score_decision = source_quality_score(
        {
            "authority_level": authority_level,
            "evidence_level": evidence_level,
            "topics": topics,
            "population": population,
            "license": license,
            "year": year,
            "existing_overlap": existing_overlap,
        }
    )
    decision = score_decision
    if not downloadable:
        decision = "manual_review" if score >= 50 else "reject"
    return {
        "candidate_id": candidate_id,
        "title": title,
        "organization": organization,
        "official_url": official_url,
        "asset_url": asset_url,
        "year": year,
        "language": language if isinstance(language, str) else ",".join(language),
        "language_preference": language if isinstance(language, list) else [language],
        "source_type": source_type,
        "population": population,
        "topics": topics,
        "life_stage_tags": life_stages,
        "intended_collection": collection,
        "use_mode": use_mode,
        "risk_scope": risk_scope,
        "clinical_only": clinical_only,
        "user_facing": user_facing,
        "authority_level": authority_level,
        "evidence_level": evidence_level,
        "license": license,
        "downloadable": downloadable,
        "auto_download": downloadable if auto_download is None else auto_download,
        "robots_allowed": "unknown_until_checked",
        "authentication_required": False,
        "estimated_size": "unknown",
        "existing_overlap": existing_overlap,
        "freshness": "current" if year and int(year) >= 2024 else "established",
        "source_quality_score": score,
        "score_parts": parts,
        "decision": decision,
        "decision_reason": f"{decision}; score={score}; {notes}".strip("; "),
        "allowed_domains": domains_for(official_url),
        "translation_group_id": stable_id(title + organization, prefix="TRG"),
        "review_status": "pending",
        "eligible_for_approval": score >= 65,
        "quality_checked": False,
        "expert_reviewed": False,
        "context": context,
        "notes": notes,
    }


CANDIDATES: list[dict[str, Any]] = [
    c("WHO_SELFHELP_2026", "Psychological self-help interventions: delivering self-help for individuals, featuring Step-by-Step and Doing What Matters in Times of Stress", "World Health Organization", "https://www.who.int/publications/i/item/9789240120785", year=2026, language=["en"], source_type="manual", collection="interventions", use_mode="direct_user_support", topics=["self_help", "stress", "guided_self_help", "problem_solving"], population=["young_adults", "adults", "workers", "university_students"], evidence_level="A", notes="Core self-help guidance; deduplicate against DWM/Step-by-Step annexes."),
    c("WHO_DWM_STRESS_2020", "Doing What Matters in Times of Stress: An Illustrated Guide", "World Health Organization", "https://www.who.int/publications/i/item/9789240003927", year=2020, language=["zh-CN", "en"], source_type="self_help_guide", collection="interventions", use_mode="direct_user_support", topics=["stress", "grounding", "acceptance", "self_compassion", "emotion_regulation"], population=["adolescents", "young_adults", "adults", "older_adults"], evidence_level="A", existing_overlap="medium", notes="Prefer official Chinese asset when available."),
    c("WHO_SH_PLUS_2021", "SELF-HELP PLUS (SH+): a group-based stress management course for adults", "World Health Organization", "https://www.who.int/publications/i/item/9789240035119", year=2021, language=["zh-CN", "en"], source_type="toolkit", collection="interventions", use_mode="direct_user_support", topics=["stress", "group_support", "mindfulness_acceptance", "grounding"], population=["adults", "workers", "people_exposed_to_trauma"], evidence_level="A", existing_overlap="medium"),
    c("WHO_PM_PLUS_2018", "Problem Management Plus (PM+): individual psychological help for adults impaired by distress in communities exposed to adversity", "World Health Organization", "https://www.who.int/publications/i/item/WHO-MSD-MER-18.5", year=2018, language=["zh-CN", "en"], source_type="intervention_manual", collection="interventions", use_mode="direct_user_support", topics=["stress", "problem_solving", "behavioral_activation", "social_support", "anxiety", "low_mood"], population=["adults", "people_exposed_to_trauma"], evidence_level="A"),
    c("WHO_PM_PLUS_TRAINING_2025", "Problem Management Plus (PM+) psychological intervention for individuals: training manual", "World Health Organization", "https://www.who.int/publications/i/item/9789240109926", year=2025, language=["en"], source_type="training_manual", collection="helping_skills", use_mode="helping_skills_only", topics=["helper_training", "supervision", "communication", "support_boundaries"], population=["adults", "family_members_supporting_others"], evidence_level="A", existing_overlap="medium"),
    c("WHO_GROUP_PM_PLUS_2020", "Group Problem Management Plus (Group PM+): group psychological help for adults impaired by distress in communities exposed to adversity", "World Health Organization", "https://www.who.int/publications/i/item/9789240008106", year=2020, language=["en"], source_type="intervention_manual", collection="interventions", use_mode="direct_user_support", topics=["stress", "group_support", "social_support", "problem_solving"], population=["adults", "people_exposed_to_trauma"], evidence_level="A", existing_overlap="medium"),
    c("WHO_GROUP_PM_PLUS_TRAINING_2026", "Group Problem Management Plus (PM+) psychological intervention: training manual", "World Health Organization", "https://www.who.int/publications/i/item/9789240122185", year=2026, language=["en"], source_type="training_manual", collection="helping_skills", use_mode="helping_skills_only", topics=["helper_training", "group_delivery", "supervision", "communication"], population=["adults"], evidence_level="A", existing_overlap="medium"),
    c("WHO_EASE_INTERVENTION_2023", "Early Adolescent Skills for Emotions (EASE)", "World Health Organization / UNICEF", "https://www.who.int/publications/i/item/9789240082755", year=2023, language=["en"], source_type="intervention_manual", collection="interventions", use_mode="direct_user_support", topics=["stress", "anxiety", "low_mood", "emotion_regulation", "caregiver_support"], population=["adolescents", "caregivers", "parents"], life_stages=["adolescent_development"], evidence_level="A"),
    c("WHO_EASE_TRAINING_2025", "Early Adolescent Skills for Emotions (EASE): training manual", "World Health Organization / UNICEF", "https://www.who.int/publications/i/item/9789240113718", year=2025, language=["en"], source_type="training_manual", collection="helping_skills", use_mode="helping_skills_only", topics=["helper_training", "adolescent_support", "caregiver_support", "communication"], population=["adolescents", "caregivers"], life_stages=["adolescent_development"], evidence_level="A", existing_overlap="medium"),
    c("WHO_THINKING_HEALTHY_2015", "Thinking Healthy: a manual for psychological management of perinatal depression", "World Health Organization", "https://www.who.int/publications/i/item/WHO-MSD-MER-15.1", year=2015, language=["zh-CN", "en"], source_type="intervention_manual", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["depression", "depressive_feelings", "perinatal_crisis", "parenthood"], population=["pregnant_people", "postpartum_people", "parents"], life_stages=["pregnancy", "postpartum", "parenthood"], evidence_level="A"),
    c("WHO_PFA_GUIDE_2011", "Psychological first aid: Guide for field workers", "World Health Organization", "https://www.who.int/publications/i/item/9789241548205", year=2011, language=["zh-CN", "en"], source_type="technical_document", collection="helping_skills", use_mode="helping_skills_only", topics=["acute_crisis", "trauma", "communication", "referral_guidance"], population=["people_exposed_to_trauma", "family_members_supporting_others"], evidence_level="A"),
    c("WHO_PFA_FACILITATOR_2013", "Psychological first aid: facilitator's manual for orienting field workers", "World Health Organization", "https://www.who.int/publications/i/item/psychological-first-aid", year=2013, language=["zh-CN", "en"], source_type="training_manual", collection="helping_skills", use_mode="helping_skills_only", topics=["acute_crisis", "helper_training", "communication"], population=["people_exposed_to_trauma", "family_members_supporting_others"], evidence_level="A", existing_overlap="medium"),
    c("WHO_HELPING_SKILLS_2025", "Foundational helping skills training manual: a competency-based approach for training helpers to support adults", "World Health Organization / UNICEF", "https://www.who.int/publications/i/item/9789240105935", year=2025, language=["en"], source_type="training_manual", collection="helping_skills", use_mode="helping_skills_only", topics=["empathy", "active_listening", "communication", "collaboration", "non_harmful_helping"], population=["adults", "family_members_supporting_others"], evidence_level="A"),
    c("WHO_MHGAP_2023", "mhGAP guideline for mental, neurological and substance use disorders, third edition", "World Health Organization", "https://www.who.int/publications/i/item/9789240084278", year=2023, language=["en"], source_type="guideline", collection="evidence", use_mode="clinical_reference_only", topics=["depression", "anxiety_disorders", "self_harm", "substance_use", "psychosis", "bipolar_disorder", "dementia"], population=["adults", "older_adults", "adolescents"], evidence_level="A", notes="Clinical reference only; ordinary counselor must not turn it into diagnosis or treatment."),
    c("WHO_SAFETY_PLANNING_2023", "Safety planning interventions", "World Health Organization", "https://www.who.int/teams/mental-health-and-substance-use/treatment-care/mental-health-gap-action-programme/evidence-centre/self-harm-and-suicide/safety-planning-interventions", year=2023, language=["en"], source_type="evidence_recommendation", collection="safety", use_mode="safety_only", topics=["self_harm", "suicidal_thoughts", "suicidal_plan", "safety_planning_principles"], population=["adolescents", "adults", "older_adults"], evidence_level="A"),
    c("WHO_LIVE_LIFE_2021", "LIVE LIFE: an implementation guide for suicide prevention in countries", "World Health Organization", "https://www.who.int/publications/i/item/9789240026629", year=2021, language=["zh-CN", "en"], source_type="implementation_guide", collection="safety", use_mode="safety_only", topics=["self_harm", "suicidal_thoughts", "acute_crisis", "referral_guidance"], population=["adolescents", "adults", "older_adults"], evidence_level="A"),
    c("WHO_WORK_GUIDELINE_2022", "WHO guidelines on mental health at work", "World Health Organization", "https://www.who.int/publications/i/item/9789240053052", year=2022, language=["zh-CN", "en"], source_type="guideline", collection="evidence", use_mode="evidence_only", topics=["work_stress", "burnout_related_distress", "return_to_work", "employment_anxiety"], population=["workers", "job_seekers", "adults"], life_stages=["career_transition"], evidence_level="A"),
    c("WHO_WORK_POLICY_BRIEF_2022", "Mental health at work: policy brief", "World Health Organization / International Labour Organization", "https://www.who.int/publications/i/item/9789240057944", year=2022, language=["en"], source_type="policy_brief", collection="governance", use_mode="agent_policy_only", topics=["work_stress", "workplace_relationship", "return_to_work"], population=["workers", "job_seekers"], life_stages=["career_transition"], evidence_level="A"),
    c("WHO_DEMENTIA_ACTION_PLAN_2017", "Global action plan on the public health response to dementia 2017-2025", "World Health Organization", "https://www.who.int/publications/i/item/global-action-plan-on-the-public-health-response-to-dementia-2017---2025", year=2017, language=["zh-CN", "en"], source_type="policy_guidance", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["dementia", "caregiving_stress", "social_support"], population=["older_adults", "caregivers", "family_members_supporting_others"], life_stages=["aging"], evidence_level="A"),
    c("CCI_ASSERTIVENESS", "Assertiveness self-help resources", "Centre for Clinical Interventions, Government of Western Australia", "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Assertiveness", year=2025, language="en", source_type="workbook_and_sheets", collection="interventions", use_mode="direct_user_support", topics=["assertiveness", "communication", "conflict_management", "relationships"], population=["university_students", "young_adults", "adults"], evidence_level="B"),
    c("CCI_DEPRESSION", "Depression self-help resources", "Centre for Clinical Interventions, Government of Western Australia", "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Depression", year=2025, language="en", source_type="workbook_and_sheets", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["depression", "low_mood", "behavioral_activation"], population=["young_adults", "adults"], evidence_level="B"),
    c("CCI_PANIC", "Panic self-help resources", "Centre for Clinical Interventions, Government of Western Australia", "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Panic", year=2025, language="en", source_type="workbook_and_sheets", collection="interventions", use_mode="direct_user_support", topics=["panic", "anxiety", "breathing_relaxation"], population=["young_adults", "adults"], evidence_level="B"),
    c("CCI_HEALTH_ANXIETY", "Health Anxiety self-help resources", "Centre for Clinical Interventions, Government of Western Australia", "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Health-Anxiety", year=2025, language="en", source_type="workbook_and_sheets", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["anxiety", "worry", "health_anxiety"], population=["young_adults", "adults"], evidence_level="B"),
    c("CCI_BIPOLAR", "Bipolar self-help resources", "Centre for Clinical Interventions, Government of Western Australia", "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Bipolar", year=2025, language="en", source_type="workbook_and_sheets", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["bipolar_disorder", "mania", "sleep"], population=["adults"], evidence_level="B"),
    c("CCI_BODY_DYSMORPHIA", "Body Dysmorphia self-help resources", "Centre for Clinical Interventions, Government of Western Australia", "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Body-Dysmorphia", year=2025, language="en", source_type="workbook_and_sheets", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["BDD", "appearance_concerns", "self_criticism"], population=["young_adults", "adults"], evidence_level="B"),
    c("CCI_DISORDERED_EATING", "Disordered Eating self-help resources", "Centre for Clinical Interventions, Government of Western Australia", "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Disordered-Eating", year=2025, language="en", source_type="workbook_and_sheets", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["eating_disorders", "body_image", "self_compassion", "severe_eating_disorder_risk"], population=["adolescents", "young_adults", "adults"], evidence_level="B"),
    c("NIMH_DEPRESSION", "Depression", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/depression", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["depression", "low_mood", "professional_help"], population=["adolescents", "young_adults", "adults", "older_adults"], evidence_level="A"),
    c("NIMH_ANXIETY", "Anxiety Disorders", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/anxiety-disorders", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["anxiety_disorders", "anxiety", "panic", "social_anxiety"], population=["adolescents", "young_adults", "adults"], evidence_level="A"),
    c("NIMH_PTSD", "Post-Traumatic Stress Disorder", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/post-traumatic-stress-disorder-ptsd", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["PTSD", "trauma", "professional_help"], population=["adolescents", "adults", "people_exposed_to_trauma"], evidence_level="A"),
    c("NIMH_OCD", "Obsessive-Compulsive Disorder", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/obsessive-compulsive-disorder-ocd", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["OCD", "anxiety_disorders", "professional_help"], population=["adolescents", "adults"], evidence_level="A"),
    c("NIMH_BIPOLAR", "Bipolar Disorder", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/bipolar-disorder", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["bipolar_disorder", "mania", "professional_help"], population=["young_adults", "adults"], evidence_level="A"),
    c("NIMH_EATING_DISORDERS", "Eating Disorders", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/eating-disorders", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["eating_disorders", "severe_eating_disorder_risk", "professional_help"], population=["adolescents", "young_adults", "adults"], evidence_level="A"),
    c("NIMH_ADHD", "Attention-Deficit/Hyperactivity Disorder", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/attention-deficit-hyperactivity-disorder-adhd", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["ADHD", "professional_help"], population=["children", "adolescents", "young_adults", "adults"], evidence_level="A"),
    c("NIMH_AUTISM", "Autism Spectrum Disorder", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/autism-spectrum-disorders-asd", year=2026, language="en", source_type="fact_sheet", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["autism", "professional_help"], population=["children", "adolescents", "young_adults", "adults", "parents", "caregivers"], evidence_level="A"),
    c("NIMH_SUICIDE_PREVENTION", "Suicide Prevention", "National Institute of Mental Health", "https://www.nimh.nih.gov/health/topics/suicide-prevention", year=2026, language="en", source_type="fact_sheet", collection="safety", use_mode="safety_only", topics=["self_harm", "suicidal_thoughts", "acute_crisis", "referral_guidance"], population=["adolescents", "young_adults", "adults", "older_adults"], evidence_level="A"),
    c("NIA_LONELINESS", "Loneliness and Social Isolation", "National Institute on Aging", "https://www.nia.nih.gov/health/loneliness-and-social-isolation", year=2026, language="en", source_type="official_web_guide", collection="professional_knowledge", use_mode="direct_user_support", topics=["loneliness", "social_isolation", "social_support"], population=["older_adults", "caregivers"], life_stages=["aging", "retirement"], evidence_level="A"),
    c("NIA_DEPRESSION_OLDER_ADULTS", "Depression and Older Adults", "National Institute on Aging", "https://www.nia.nih.gov/health/mental-and-emotional-health/depression-and-older-adults", year=2026, language="en", source_type="official_web_guide", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["depression", "low_mood", "aging", "professional_help"], population=["older_adults", "caregivers"], life_stages=["aging", "retirement"], evidence_level="A"),
    c("SAMHSA_TRAUMA_INFORMED_CARE", "Practical Guide for Implementing a Trauma-Informed Approach", "Substance Abuse and Mental Health Services Administration", "https://www.samhsa.gov/resource/dbhis/practical-guide-implementing-trauma-informed-approach", year=2023, language="en", source_type="guide", collection="helping_skills", use_mode="helping_skills_only", topics=["trauma", "communication", "non_harmful_helping", "safety"], population=["people_exposed_to_trauma", "family_members_supporting_others"], evidence_level="A"),
    c("SAMHSA_FAMILY_SUPPORT", "Family, Parent and Caregiver Peer Support", "Substance Abuse and Mental Health Services Administration", "https://www.samhsa.gov/families", year=2026, language="en", source_type="official_web_guide", collection="professional_knowledge", use_mode="direct_user_support", topics=["family_relationships", "caregiving_stress", "communication", "support_boundaries"], population=["parents", "caregivers", "family_members_supporting_others"], evidence_level="A"),
    c("VA_SKILLS_PSYCHOLOGICAL_RECOVERY", "Skills for Psychological Recovery", "VA National Center for PTSD", "https://www.ptsd.va.gov/professional/treat/type/SPR/SPR_manual.asp", year=2026, language="en", source_type="manual", collection="helping_skills", use_mode="helping_skills_only", topics=["trauma", "problem_solving", "social_support", "anger", "sleep", "grief"], population=["people_exposed_to_trauma", "parents", "caregivers"], evidence_level="B"),
    c("NICE_SELF_HARM", "Self-harm: assessment, management and preventing recurrence", "National Institute for Health and Care Excellence", "https://www.nice.org.uk/guidance/ng225", year=2022, language="en", source_type="clinical_guideline", collection="safety", use_mode="safety_only", topics=["self_harm", "suicidal_thoughts", "safety_planning_principles", "referral_guidance"], population=["adolescents", "adults", "older_adults"], evidence_level="A"),
    c("NICE_DEPRESSION", "Depression in adults: treatment and management", "National Institute for Health and Care Excellence", "https://www.nice.org.uk/guidance/ng222", year=2022, language="en", source_type="clinical_guideline", collection="evidence", use_mode="clinical_reference_only", topics=["depression", "professional_help", "clinical_boundary"], population=["adults", "older_adults"], evidence_level="A"),
    c("NICE_GAD_PANIC", "Generalised anxiety disorder and panic disorder in adults", "National Institute for Health and Care Excellence", "https://www.nice.org.uk/guidance/cg113", year=2011, language="en", source_type="clinical_guideline", collection="evidence", use_mode="clinical_reference_only", topics=["anxiety_disorders", "panic", "professional_help"], population=["adults"], evidence_level="A"),
    c("CN_NHC_HEALTH_LITERACY_2024", "中国公民健康素养——基本知识与技能（2024年版）", "国家卫生健康委员会", "https://www.nhc.gov.cn/", year=2024, language="zh-CN", source_type="official_policy", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["mental_health_literacy", "sleep", "anxiety", "depression", "scientific_help_seeking"], population=["children", "adolescents", "young_adults", "adults", "older_adults"], evidence_level="A", auto_download=False, notes="Homepage candidate; exact official asset may need manual confirmation if search results change."),
    c("CN_MOE_HIGHER_ED_MH_GUIDE_2018", "高等学校学生心理健康教育指导纲要", "中华人民共和国教育部", "https://www.moe.gov.cn/srcsite/A12/moe_1407/s3020/201807/t20180713_342992.html", year=2018, language="zh-CN", source_type="policy_guideline", collection="campus_support", use_mode="agent_policy_only", topics=["university_students", "campus_support", "academic_pressure", "counselling_services"], population=["university_students", "students"], life_stages=["college_transition"], evidence_level="A"),
    c("CN_MOE_STUDENT_MH_ACTION_2023_2025", "全面加强和改进新时代学生心理健康工作专项行动计划（2023—2025年）", "中华人民共和国教育部等十七部门", "https://www.moe.gov.cn/srcsite/A17/moe_943/moe_946/202305/t20230511_1059219.html", year=2023, language="zh-CN", source_type="policy_plan", collection="campus_support", use_mode="agent_policy_only", topics=["student_mental_health", "campus_support", "children", "adolescents", "university_students"], population=["children", "adolescents", "students", "university_students"], life_stages=["child_development", "adolescent_development", "college_transition"], evidence_level="A"),
    c("CN_MOE_SCHOOL_MH_GUIDE", "中小学心理健康教育指导纲要", "中华人民共和国教育部", "https://www.moe.gov.cn/", year=2026, language="zh-CN", source_type="policy_guideline", collection="governance", use_mode="agent_policy_only", topics=["children", "adolescents", "school_support", "parent_support"], population=["children", "adolescents", "parents", "caregivers"], life_stages=["child_development", "adolescent_development"], evidence_level="A", auto_download=False, notes="Exact official page should be confirmed during manual source review."),
    c("UNICEF_ADOLESCENT_MH", "Mental health and psychosocial support for adolescents", "UNICEF", "https://www.unicef.org/mental-health", year=2026, language="en", source_type="official_web_guide", collection="professional_knowledge", use_mode="psychoeducation_only", topics=["adolescent_development", "stress", "anxiety", "low_mood", "social_relationships"], population=["adolescents", "parents", "caregivers"], life_stages=["adolescent_development"], evidence_level="A"),
    c("UNICEF_PARENTING_MH", "Parent and caregiver mental health support", "UNICEF", "https://www.unicef.org/parenting/mental-health", year=2026, language="en", source_type="official_web_guide", collection="professional_knowledge", use_mode="direct_user_support", topics=["parent_child_relationship", "caregiving_stress", "communication", "self_compassion"], population=["parents", "caregivers", "children", "adolescents"], life_stages=["parenthood"], evidence_level="A"),
]


def candidates_by_id() -> dict[str, dict[str, Any]]:
    return {item["candidate_id"]: item for item in CANDIDATES}


def registry_source_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    collection = candidate["intended_collection"]
    url = candidate["official_url"]
    allowed_domains = candidate.get("allowed_domains") or domains_for(url)
    source = {
        "id": candidate["candidate_id"],
        "enabled": bool(candidate.get("decision") in {"strong_include", "include_if_gap", "manual_review"}),
        "auto_download": bool(candidate.get("auto_download")) and candidate.get("decision") in {"strong_include", "include_if_gap"},
        "priority": "P0" if candidate.get("use_mode") in {"safety_only", "direct_user_support"} else "P1",
        "organization": candidate["organization"],
        "title": candidate["title"],
        "version": "v2",
        "year": candidate.get("year"),
        "language_preference": candidate.get("language_preference") or [candidate.get("language") or "en"],
        "language": candidate.get("language_preference", [candidate.get("language", "")])[0],
        "translation_group_id": candidate.get("translation_group_id"),
        "source_type": candidate.get("source_type", ""),
        "target_collection": collection,
        "collection": collection,
        "topics": candidate.get("topics") or [],
        "topic_tags": candidate.get("topics") or [],
        "population_tags": candidate.get("population") or [],
        "life_stage_tags": candidate.get("life_stage_tags") or [],
        "use_mode": candidate.get("use_mode"),
        "risk_scope": candidate.get("risk_scope"),
        "user_facing": bool(candidate.get("user_facing")),
        "clinical_only": bool(candidate.get("clinical_only")),
        "evidence_level": candidate.get("evidence_level", "source_unverified"),
        "source_authority": candidate.get("authority_level", "tier_a"),
        "official_page_url": url,
        "official_url": url,
        "download_url": candidate.get("asset_url") or "",
        "license": candidate.get("license", ""),
        "license_note": candidate.get("license", ""),
        "review_status": candidate.get("review_status", "pending"),
        "eligible_for_approval": bool(candidate.get("eligible_for_approval")),
        "quality_checked": False,
        "expert_reviewed": False,
        "last_checked_at": "",
        "document_hash": "",
        "download": {
            "mode": "follow_official_download_link" if candidate.get("downloadable") else "html_page",
            "allowed_domains": allowed_domains,
            "preferred_mime_types": ["application/pdf", "text/html"],
            "allowed_extensions": [".pdf", ".html", ".htm", ".doc", ".docx"],
            "max_assets": 4,
        },
        "notes": candidate.get("notes", ""),
    }
    if collection == "safety" or candidate.get("use_mode") == "safety_only":
        source["user_facing"] = False
        source["risk_scope"] = "safety_route_only"
    if candidate.get("use_mode") in {"clinical_reference_only", "evidence_only", "agent_policy_only", "helping_skills_only"}:
        source["user_facing"] = False
    return source
