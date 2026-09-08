# Engineering Maturity and Readiness

These scores are engineering maturity estimates from the observed code/config/runtime state, not scientific, clinical, or benchmark metrics.

| Area | Score / 10 | Reason |
|---|---:|---|
| Core Chat | 8 | End-to-end conversation path, persistence, ARK call, and safety post-processing are wired |
| Multimodal | 5 | Image path active; audio configured but unverified; video partial; async jobs unwired |
| Risk/Safety | 6 | Risk-first deterministic branch and safety rewrite exist; rule calibration and LLM review are incomplete |
| Psychological State | 7 | Typed local analyzer runs and reaches strategy/counselor; it is heuristic, not clinical inference |
| Strategy | 7 | Planner output affects prompt constraints and RAG route; no learned planner |
| RAG | 7 | Production hybrid index and metadata boundaries exist; coverage split and benchmark/runtime parity remain issues |
| Knowledge Base | 7 | 13,166 chunk records, review states, manifests, and publication path exist; source/review gaps remain |
| Evaluation | 5 | Local runner, cached results, human review, and heuristics exist; official judge/benchmark execution is partial |
| RBAC | 7 | Backend guards, roles, permissions, owner checks, and sanitization are active |
| Data/Privacy | 5 | Session memory/privacy routes exist; long-term semantics, retention, export, and complete audit evidence are incomplete |
| Production Readiness | 3 | Current app environment is development; provider and deployment hardening are not fully verified |
| Testing | 6 | 109 backend tests pass; frontend tests and broad provider/runtime tests are absent |
| Observability | 4 | Request metrics/traces exist; cost rates, dashboards, and alerting are incomplete |

## Readiness Estimates

| Target | Estimate | Meaning |
|---|---:|---|
| Demo ready | 82% | Core chat, visible Agent V2/RAG/RBAC surfaces, and local build/test evidence exist |
| Competition ready | 65% | Strong engineering substrate, but safety evidence, benchmark claims, multimodal verification, and polish remain |
| Production ready | 35% | Operational, privacy, safety validation, provider reliability, and deployment gates are incomplete |

These percentages are deliberately coarse engineering estimates and should not be presented as model quality or clinical safety scores.

## P0 Blockers

| ID | Problem | Evidence | Complexity | Blocking competition |
|---|---|---|---|---|
| P0-01 | Production secret injection/rotation is not separately verified | Current values configured but `APP_ENV=development` | MEDIUM | YES |
| P0-02 | Risk semantics lack labeled calibration for history/quotes/third-party/jokes | Rule diagnostics show divergent conservative outcomes | HIGH | YES |
| P0-03 | RAG production dense coverage is zero for safety/campus/evidence/governance collections | Production dense manifest | HIGH | YES |
| P0-04 | Official benchmark/judge claims are not active | Latest RAG benchmark is staged; local judge is heuristic | HIGH | YES |
| P0-05 | Active prompt source and legacy prompt file are split | Inline counselor prompt is runtime source | LOW | YES |

## P1

- P1-01: Verify ASR with a controlled fixture and add multimodal provider contract tests.
- P1-02: Implement a worker or remove the async job surface from supported claims.
- P1-03: Add frontend route/method regression tests and structured 405 diagnostics.
- P1-04: Add cost rates, provider latency/error dashboards, and retry/backoff policy evidence.
- P1-05: Reconcile registry source count, chunk source IDs, and production index manifests.

## P2

- P2-01: Connect fine-tuned counselor inference behind an explicit experiment switch.
- P2-02: Add blinded human review and inter-rater agreement reporting.
- P2-03: Add user-visible memory retention/export/deletion controls.
- P2-04: Consolidate legacy paths after runtime usage evidence is collected.
