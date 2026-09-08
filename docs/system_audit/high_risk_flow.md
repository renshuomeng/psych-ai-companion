# High-Risk Flow

## Observed Decision Order

`incoming text and multimodal text -> rule risk agent -> high-risk branch -> fixed crisis-support/referral response -> persistence and metrics`.

For high risk, the coordinator skips the ordinary Counselor and RAG path. The response is intentionally deterministic and does not require the configured ARK provider.

## Active Safeguards

- Chinese and English high-risk terms are recognized.
- Negation, quoted/reference text, third-party reports, plan terms, means terms, and immediacy dimensions are tracked.
- Safety-related metadata is stored in the risk state and trace.
- Ordinary RAG is skipped on high and medium risk routes.

## Known Semantic Limits

The detector is a keyword/rule system, not a calibrated classifier. The current rules can classify a historical self-harm statement as high risk because past-time handling is incomplete. Third-party and quoted statements are distinguished but can still receive medium risk. A joking self-harm phrase is currently treated conservatively as high risk. These are product-behavior findings, not changes made by this audit.

## Status

- High-risk referral branch: `IMPLEMENTED_AND_ACTIVE`.
- Risk interpretation quality: `PARTIALLY_IMPLEMENTED`.
- Clinical risk calibration and validated recall/precision evidence: `NOT_IMPLEMENTED`.
- LLM safety review: `IMPLEMENTED_BUT_NOT_WIRED`.

## Exact Runtime Branch

`run_multimodal_flow()` combines user text, audio/video transcript, image OCR, and video OCR into `risk_sources`, then calls `assess_risk_sources()`. Text-only `run_chat_flow()` calls `assess_risk()` directly. Both paths run RiskAgent before ordinary Agent V2 work.

When `risk["level"] == "high"`, the coordinator creates `CRISIS_REFERRAL_REPLY`, adds a crisis-referral intervention, records the user/assistant turns and request metric in the multimodal path, marks retrieval as `skipped_high_risk`, and does not call PsychologicalStateAnalyzer, StrategyPlanner, RAG, or CounselorAgent. `review_response()` then sees the crisis result and preserves/enforces the crisis template. The provider metadata has no external model call for this branch.

The normal path is only entered after the high-risk check. A failed ARK call therefore cannot overwrite a high-risk response because CounselorAgent is never invoked in that branch. Medium risk is not the same branch: it can proceed through ordinary generation, while the RAG router's rule set avoids ordinary knowledge retrieval for medium safety-sensitive cases.

## Context Cases Observed in Rule Diagnostics

| Input pattern | Current rule outcome | Finding |
|---|---|---|
| Negated self-harm statement | low | Negation handling exists |
| Historical self-harm statement | high | Past-time qualification is not fully separated |
| Third-party report | medium | Third-party dimension exists but is conservative |
| Movie/quoted statement | medium | Quotation/reference context is tracked but not fully neutralized |
| “Just joking” self-harm phrase | high | Conservative false-positive risk |

These are code-level rule outcomes, not clinical sensitivity/specificity measurements.

