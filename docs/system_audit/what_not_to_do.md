# What Not to Do Yet

- Do not claim the current local heuristic evaluation is an official benchmark result.
- Do not enable public access until production secret injection, rotation, and restart persistence are verified separately from the current development environment.
- Do not assume the LLM safety review is active because a config flag or metadata field exists.
- Do not switch to the fine-tuned model merely because SFT files were generated.
- Do not publish pending or rejected KB content into production indexes without review evidence.
- Do not treat the legacy SQLite knowledge tables as the active RAG source without checking the RAG V1 settings.
- Do not enable global memory without explicit retention, consent, deletion, and privacy behavior.
- Do not expose provider metadata, traces, or user-sensitive state to roles that lack the corresponding permission.
- Do not use the current database for destructive test runs; use isolated temporary databases.
- Do not infer that a frontend 405 message identifies the actual failing route; inspect the browser request method and backend route contract.

