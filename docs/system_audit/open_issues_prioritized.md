# Open Issues by Priority

## P0: Before Any Public or Competition-Claimed Production Use

1. Verify production secret injection, rotation, and restart persistence for `AUTH_JWT_SECRET` and `PUBLIC_SESSION_SECRET`; current development configuration reports them configured.
2. Establish a documented production KB/index release process and verify collection coverage, especially production safety and campus-support coverage.
3. Validate high-risk detection with a labeled, privacy-safe test set covering negation, history, quotation, third-party report, ambiguity, and means/immediacy.
4. Define the authoritative prompt/model/RAG data plane and document or retire the parallel legacy paths.
5. Add provider outage, retry, timeout, cost, and audit observability before enabling wider access.

## P1: Required for a Credible Multimodal Product

1. Verify the configured speech ASR provider with a controlled non-production fixture, then add TTS only with an explicit safety/consent design.
2. Implement and operate a real job worker if async multimodal APIs are retained.
3. Add independent file malware/content checks and retention controls.
4. Wire a reviewed safety-evaluation path; do not assume an LLM safety call is active because a setting exists.
5. Add frontend regression tests and route/method contract tests to improve diagnosis of generic 405 errors.

## P2: Research and Competition Strengthening

1. Wire fine-tuned model inference behind a controlled model switch and compare it with the base model.
2. Integrate official benchmark runners or clearly label all local heuristic scores as internal smoke evidence.
3. Add blinded human review sampling, inter-rater agreement, and safety-specific outcome metrics.
4. Implement user-visible memory controls, retention, export, and deletion semantics.
5. Add cost-rate configuration and per-request budget dashboards.

