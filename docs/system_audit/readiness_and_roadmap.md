# Readiness and Roadmap

## Current Readiness Statement

The evidence supports local development, controlled internal testing, and continued research iteration. It does not support an unconditional production-readiness claim for a mental-health-facing service.

## Recommended Sequence

### Gate 1: Configuration and Provenance

Verify production secret injection/rotation, preserve environment-specific configuration, add Git provenance, and define the active prompt/model/index versions in every run record.

### Gate 2: Safety and Data Plane

Create labeled risk and safety cases, measure false positives/negatives, verify high-risk referral behavior, and reconcile registry/index/database knowledge sources.

### Gate 3: Multimodal Reliability

Enable ASR only after provider checks, implement or remove async jobs, add upload security/retention, and test provider failures.

### Gate 4: Evaluation Claims

Separate smoke heuristics, human review, and official benchmark scores. Add a real judge or blinded human protocol before publishing quality claims.

### Gate 5: Model Research

Only after the baseline is stable, connect the SFT model through an explicit switch and run paired comparisons on identical cases.

