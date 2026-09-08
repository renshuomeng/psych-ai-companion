from __future__ import annotations

import re
from collections import Counter


NAVIGATION_PATTERNS = [
    r"skip to (main )?content",
    r"cookie(s)? policy",
    r"accept all cookies",
    r"related content",
    r"share this page",
    r"print this page",
    r"back to top",
    r"privacy notice",
]


def looks_mojibake(text: str) -> bool:
    suspicious = sum(text.count(token) for token in ["鈥", "锛", "绛", "涓", "€", "�"])
    return suspicious > max(8, len(text) * 0.02)


def _strip_page_number(line: str) -> str:
    stripped = line.strip()
    if re.fullmatch(r"(page\s*)?\d{1,4}(\s*/\s*\d{1,4})?", stripped, flags=re.I):
        return ""
    if re.fullmatch(r"[-–—]?\s*\d{1,4}\s*[-–—]?", stripped):
        return ""
    return line


def _remove_repeated_short_lines(lines: list[str]) -> list[str]:
    normalized = [re.sub(r"\s+", " ", line).strip().lower() for line in lines if line.strip()]
    counts = Counter(item for item in normalized if 3 <= len(item) <= 100)
    output: list[str] = []
    for line in lines:
        key = re.sub(r"\s+", " ", line).strip().lower()
        if counts.get(key, 0) >= 4:
            continue
        output.append(line)
    return output


def _remove_duplicate_paragraphs(paragraphs: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for paragraph in paragraphs:
        key = re.sub(r"\s+", " ", paragraph).strip().lower()
        if len(key) > 40 and key in seen:
            continue
        seen.add(key)
        output.append(paragraph)
    return output


def clean_knowledge_text(text: str) -> tuple[str, list[str]]:
    issues: list[str] = []
    if looks_mojibake(text):
        issues.append("possible_mojibake")
    text = text.replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_strip_page_number(line) for line in text.splitlines()]
    cleaned_lines: list[str] = []
    for line in lines:
        compact = re.sub(r"\s+", " ", line).strip()
        if not compact:
            cleaned_lines.append("")
            continue
        if any(re.search(pattern, compact, flags=re.I) for pattern in NAVIGATION_PATTERNS):
            continue
        cleaned_lines.append(compact)
    cleaned_lines = _remove_repeated_short_lines(cleaned_lines)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    paragraphs = _remove_duplicate_paragraphs(paragraphs)
    return "\n\n".join(paragraphs).strip(), issues
