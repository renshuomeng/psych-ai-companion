# CARE-Psy Current Architecture

Generated: 2026-08-10

```mermaid
flowchart TD
    U["User Input: text, image, audio, video, check-in"] --> FE["React/Vite Frontend"]
    FE --> API["FastAPI API"]
    API --> MM["MultimodalAgent / media services"]
    MM --> IMG["Image analysis: OCR, visual cues"]
    MM --> AUD["Audio transcription"]
    MM --> VID["Video analysis: provider video or keyframe fallback"]
    IMG --> EV["Unified Evidence Objects"]
    AUD --> EV
    VID --> EV
    API --> RISK["RiskAgent: rule-first safety assessment"]
    EV --> RISK
    RISK -->|high risk| CRISIS["Fixed Crisis Referral"]
    RISK -->|low / medium| MEM["MemoryAgent / MemoryService"]
    MEM --> RC["Recent Conversation"]
    MEM --> SUM["Rolling Structured Summary"]
    MEM --> PREF["User Preference Memory"]
    MEM --> RS["Independent Risk State"]
    RISK --> EMO["EmotionAgent"]
    EV --> EMO
    EMO --> INT["InterventionAgent"]
    API --> RET["RetrievalService"]
    RET --> DENSE["Dense local vector retrieval"]
    RET --> FTS["SQLite FTS / keyword retrieval"]
    RET --> META["Psychological metadata: emotion, cause, strategy, risk"]
    DENSE --> FUSION["Fusion + Rerank"]
    FTS --> FUSION
    META --> FUSION
    FUSION --> RAG["Emotion-aware RAG context + source cards"]
    RC --> CTX["ContextBuilder"]
    SUM --> CTX
    PREF --> CTX
    RS --> CTX
    RAG --> CTX
    EV --> CTX
    CTX --> COUNSELOR["CounselorAgent: Doubao / Ark"]
    COUNSELOR --> SAFETY["SafetyAgent"]
    SAFETY --> REPLY["Personalized Reply"]
    REPLY --> FE
    INT --> FE
    REPLY --> METRICS["Request Metrics"]
    REPLY --> MEMUP["Memory Update"]
    CRISIS --> SAFETY
```

## Notes

- Risk and safety remain ordered gates; they are not parallelized after generation.
- RAG, memory, and metrics can fail independently without disabling high-risk detection.
- Visual affect from images/videos is explicitly low-weight and cannot diagnose mental state or trigger high risk by itself.
- The current vector backend is SQLite with deterministic local embeddings; ChromaDB is not active because the package is not installed in the current Python environment.
