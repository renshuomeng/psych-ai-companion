# Incomplete Code Inventory

This inventory distinguishes present code from active, complete product behavior.

| Area | Evidence | Status |
|---|---|---|
| STT router/service | Placeholder implementation and message indicating not implemented | `MOCK_OR_PLACEHOLDER` |
| TTS | No runtime implementation found | `NOT_IMPLEMENTED` |
| Video companion | Frontend page with placeholder-level behavior | `MOCK_OR_PLACEHOLDER` |
| Async multimodal jobs | CRUD/status surface without discovered worker | `IMPLEMENTED_BUT_NOT_WIRED` |
| Speech configuration | Service exists, current env disabled | `IMPLEMENTED_BUT_DISABLED` |
| Fine-tuned runtime | SFT artifacts exist, no runtime model selection/use | `NOT_IMPLEMENTED` |
| LLM safety review | Setting/field exists, active safety is rules only | `IMPLEMENTED_BUT_NOT_WIRED` |
| LLM semantic memory | No active semantic memory implementation | `NOT_IMPLEMENTED` |
| Global memory | Explicitly disabled by setting | `IMPLEMENTED_BUT_DISABLED` |
| Official benchmark judge | Registry/metadata only or local compatible scoring | `PARTIALLY_IMPLEMENTED` |
| Frontend automated tests | No test script observed | `NOT_IMPLEMENTED` |
| Stable JWT/session secrets | Config keys exist but current values absent | `PARTIALLY_IMPLEMENTED` |
| Cost tracking | Cost fields/config exist without configured rates or verified accounting | `NOT_IMPLEMENTED` |
| Admin audit log evidence | Table exists but current row count is zero | `IMPLEMENTED_BUT_NOT_WIRED` |
| Human review evidence | Page/route exists, current review table has zero rows | `IMPLEMENTED_AND_ACTIVE` |

The status reflects the audit date and current configuration, not a claim that the code can never be completed.


