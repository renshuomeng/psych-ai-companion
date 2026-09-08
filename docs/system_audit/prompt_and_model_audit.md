# Prompt and Model Audit

## Runtime Model

Normal counseling uses `backend/agents/counselor_agent.py` and `services.ark_client.generate_text`, targeting the configured Doubao model ID. The counselor prompt is inline and includes risk, emotion, Agent V2 state, strategy, RAG/citations, and response constraints. It instructs against diagnosis, medication instructions, and treatment promises.

## Prompt Source Split

`backend/prompts/counselor_prompt.txt` exists but is not the observed runtime source. This creates a prompt-governance risk: editing or reviewing the file alone may not change production behavior.

## Provider Behavior

ARK uses the Responses endpoint. Retry coverage exists for timeout/transport and 429/5xx responses, with three attempts and no exponential backoff. Development mock mode is available but disabled in the current environment.

## Fine-Tuning

SFT preparation is present. The selected SFT report describes 2,000 combined records from three sources with zero Ark validation errors. No fine-tuned model ID or runtime switch is wired into the active counselor path.

| Item | Status |
|---|---|
| Configured base model call | `IMPLEMENTED_AND_ACTIVE` |
| Runtime prompt governance | `PARTIALLY_IMPLEMENTED` |
| Provider retry | `IMPLEMENTED_AND_ACTIVE` |
| Fine-tuned artifact preparation | `IMPLEMENTED_AND_ACTIVE` |
| Fine-tuned runtime inference | `NOT_IMPLEMENTED` |
| Model A/B evaluation | `NOT_IMPLEMENTED` |


