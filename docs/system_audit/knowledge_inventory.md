# Knowledge Base Inventory

## Recomputed Chunk State

Counts below were recomputed from `backend/data/knowledge_base/chunks/{approved,pending,rejected}/chunks.jsonl` on 2026-09-07.

| Dimension | Count |
|---|---:|
| Chunk records | 13,166 |
| Approved | 6,631 |
| Pending | 1,648 |
| Rejected | 4,887 |
| Unique source IDs in chunks | 59 |
| Unique document IDs | 320 |
| English chunks | 12,088 |
| Chinese chunks | 1,078 |
| `direct_user_support` | 6,954 |
| `psychoeducation_only` | 1,581 |
| `helping_skills_only` | 2,500 |
| `safety_only` | 817 |
| `evidence_only` | 3 |
| `clinical_reference_only` | 968 |
| `agent_policy_only` | 343 |
| `risk_scope=normal` | 12,349 |
| `risk_scope=safety_route_only` | 817 |
| `user_facing=true` | 6,954 |
| `clinical_only=true` | 971 |
| `exclude_from_index=true` | 0 |

## Physical Pipeline Files

Observed counts: raw 850 files, parsed 320 files, cleaned 320 files, processed 1 file, sources 5 files. Backups are present and intentionally excluded from current-state counts.

## Source Families

| Family | Sources | Documents | Chunks | Language | Review summary |
|---|---:|---:|---:|---|---|
| WHO | 20 | 33 | 5,894 | 4,891 en / 1,003 zh-CN | 1,305 approved / 1,271 pending / 3,318 rejected |
| CCI | 16 | 249 | 6,248 | 6,248 en | 5,090 approved / 171 pending / 987 rejected |
| NHS | 6 | 13 | 159 | 159 en | 143 approved / 16 rejected |
| NIMH | 9 | 10 | 163 | 163 en | 80 approved / 15 pending / 68 rejected |
| NICE | 3 | 6 | 531 | 531 en | 145 pending / 386 rejected |
| China official | 3 | 7 | 75 | 75 zh-CN | 75 rejected |
| UNICEF | 1 | 1 | 19 | 19 en | 13 approved / 6 rejected |
| SAMHSA | 0 | 0 | 0 | - | no chunk records observed |
| NIA | 0 | 0 | 0 | - | no chunk records observed |
| Other / VA | 1 | 1 | 77 | 77 en | 46 pending / 31 rejected |

The registry configuration reports 67 enabled sources, while chunk records currently contain 59 source IDs. This difference is itself an audit finding: enabled registry sources do not all have chunk records.
