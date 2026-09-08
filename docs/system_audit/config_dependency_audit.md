# Configuration and Dependency Audit

## Current Runtime Configuration

| Setting | Observed state |
|---|---|
| `APP_ENV` | `development` |
| `PUBLIC_ACCESS_ENABLED` | `false` |
| `ENABLE_DEV_MOCK` | `false` |
| `AUTH_JWT_SECRET` | configured |
| `PUBLIC_SESSION_SECRET` | configured |
| `INITIAL_ADMIN_PASSWORD` | configured |
| ARK provider/model | configured |
| speech provider API key | configured; ASR runtime not verified |
| input/output token cost rates | unset |
| RAG V1 production | enabled |
| RAG fallback | disabled |

## Dependencies

FastAPI, React 19, Vite 6, Python 3.13, SQLite, ARK, BM25, Chroma, local BGE-M3 embeddings, ffmpeg, and ffprobe are present in the observed environment. Provider credential presence was inferred only from application configuration and non-secret status; no secret values are included.

## Deployment Findings

Docker builds the frontend and runs Uvicorn with Caddy. Compose persists uploads and SQLite, but the Docker ignore/deployment arrangement does not clearly persist the KB registry/index/model assets as a mutable runtime volume. This can make index publication and rollback image-dependent.

## Status

Local development execution: `IMPLEMENTED_AND_ACTIVE`.

Production configuration hardening: `PARTIALLY_IMPLEMENTED`.

Cost accounting and budget enforcement: `NOT_IMPLEMENTED`.

