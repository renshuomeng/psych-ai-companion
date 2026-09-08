# CARE-Psy SFT Dataset Selection Summary

- System prompt path: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\backend\prompts\system_prompt.txt`
- Combined Ark JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\ark\care_psy_sft_selected_2000_ark.jsonl`
- Combined records: 2000

## Dataset Outputs

### cpsdd

- Raw records: 54508
- Normalized records: 54508
- Scored eligible records: 32905
- Refined candidate records: 1937
- Final selected records: 1000
- Selected JSON: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_selected_1000.json`
- Selected JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_selected_1000.jsonl`
- Ark JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_selected_1000_ark.jsonl`
- Refined candidate JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\cpsdd\cpsdd_candidate_refined_1937.jsonl`
- Report: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\cpsdd_selection_report.md`
- Final severity distribution: `{"medium":556,"low":438,"high":6}`

### psydial_d4

- Raw records: 2382
- Normalized records: 2382
- Scored eligible records: 1348
- Refined candidate records: 785
- Final selected records: 400
- Selected JSON: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_selected_400.json`
- Selected JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_selected_400.jsonl`
- Ark JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_selected_400_ark.jsonl`
- Refined candidate JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\psydial_d4\psydial_d4_candidate_refined_785.jsonl`
- Report: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\psydial_d4_selection_report.md`
- Final severity distribution: `{"medium":345,"low":55}`

### soulchat

- Raw records: 258353
- Normalized records: 258353
- Scored eligible records: 97454
- Refined candidate records: 980
- Final selected records: 600
- Selected JSON: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_selected_600.json`
- Selected JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_selected_600.jsonl`
- Ark JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_selected_600_ark.jsonl`
- Refined candidate JSONL: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\processed\soulchat\soulchat_candidate_refined_980.jsonl`
- Report: `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion\training\reports\soulchat_selection_report.md`
- Final severity distribution: `{"medium":274,"low":254,"high":72}`

## Ark Validation

```json
[
  {
    "path": "C:\\Users\\renshuomeng\\Documents\\Codex\\2026-06-30\\ban\\psych-ai-companion\\training\\processed\\cpsdd\\cpsdd_selected_1000_ark.jsonl",
    "line_count": 1000,
    "role_counts": {
      "system": 1000,
      "user": 7350,
      "assistant": 7350
    },
    "error_count": 0,
    "errors": []
  },
  {
    "path": "C:\\Users\\renshuomeng\\Documents\\Codex\\2026-06-30\\ban\\psych-ai-companion\\training\\processed\\psydial_d4\\psydial_d4_selected_400_ark.jsonl",
    "line_count": 400,
    "role_counts": {
      "system": 400,
      "user": 12563,
      "assistant": 12563
    },
    "error_count": 0,
    "errors": []
  },
  {
    "path": "C:\\Users\\renshuomeng\\Documents\\Codex\\2026-06-30\\ban\\psych-ai-companion\\training\\processed\\soulchat\\soulchat_selected_600_ark.jsonl",
    "line_count": 600,
    "role_counts": {
      "system": 600,
      "user": 3648,
      "assistant": 3648
    },
    "error_count": 0,
    "errors": []
  },
  {
    "path": "C:\\Users\\renshuomeng\\Documents\\Codex\\2026-06-30\\ban\\psych-ai-companion\\training\\processed\\ark\\care_psy_sft_selected_2000_ark.jsonl",
    "line_count": 2000,
    "role_counts": {
      "system": 2000,
      "user": 23561,
      "assistant": 23561
    },
    "error_count": 0,
    "errors": []
  }
]
```
