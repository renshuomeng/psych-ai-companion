# Multimodal Audit

## Current Paths

The primary `MultimodalChat` page uploads attachments through the conversation API. The backend multimodal agent can process image, audio, and video inputs and merges their extracted text/context before risk-first orchestration.

| Capability | Evidence | Status |
|---|---|---|
| Image input and vision extraction | ARK vision service with development mock fallback | `IMPLEMENTED_AND_ACTIVE` |
| Audio input and Volc ASR | Service exists and current `VOLC_SPEECH_API_KEY` is configured; no paid/provider runtime call was made | `PARTIALLY_IMPLEMENTED` |
| Video input | Provider video path, keyframe image fallback, ffmpeg audio extraction | `PARTIALLY_IMPLEMENTED` |
| Upload validation | Extension, MIME, size, and probe checks | `IMPLEMENTED_AND_ACTIVE` |
| Attachment ownership checks | File router permission and owner checks | `IMPLEMENTED_AND_ACTIVE` |
| Async multimodal jobs | Queue/create/get/cancel APIs exist; no worker/process transition was found and frontend main path does not use them | `IMPLEMENTED_BUT_NOT_WIRED` |
| `/api/stt` | Placeholder service/router path | `MOCK_OR_PLACEHOLDER` |
| TTS | No runtime implementation found | `NOT_IMPLEMENTED` |
| Video companion page | Present but placeholder-level experience | `MOCK_OR_PLACEHOLDER` |

## Deployment Dependency

`ffmpeg` and `ffprobe` are available locally. This confirms tool availability, not successful provider-level audio/video generation. The current speech API key is configured, but ASR runtime success was not verified because this audit did not upload audio or call the paid provider.

## Safety Boundary

Uploaded files are validated for type and size. No independent antivirus, content moderation, or human review gate was found before provider processing.

## Actual Audio Path

`conversation_service.process_attachments()` calls `speech_service.transcribe_audio()`, which builds the Volc flash request, extracts a transcript, and places it into `audio_transcript` before `run_multimodal_flow()`. A missing or rejected provider call becomes an attachment error; the current audit did not exercise that paid call.

