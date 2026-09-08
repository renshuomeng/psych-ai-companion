import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from schemas.errors import AppError


SUPPORTED_KNOWLEDGE_EXTENSIONS = {".md", ".txt", ".docx", ".pdf", ".json", ".jsonl", ".html", ".htm"}


@dataclass
class ParsedDocument:
    title: str
    sections: list[dict[str, str]]
    raw_text: str


def _clean_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sections_from_markdown(text: str, fallback_title: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_title = fallback_title
    buffer: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if buffer:
                sections.append({"section": current_title, "content": _clean_text("\n".join(buffer))})
                buffer = []
            current_title = stripped.lstrip("#").strip() or fallback_title
        else:
            buffer.append(line)
    if buffer:
        sections.append({"section": current_title, "content": _clean_text("\n".join(buffer))})
    return [section for section in sections if section["content"]]


def _sections_from_plain_text(text: str, fallback_title: str) -> list[dict[str, str]]:
    chunks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    sections: list[dict[str, str]] = []
    current_title = fallback_title
    buffer: list[str] = []
    heading_pattern = re.compile(r"^([一二三四五六七八九十]+[、.．]|[0-9]+[、.．])?\s*[\u4e00-\u9fffA-Za-z0-9 ]{2,28}$")
    for chunk in chunks:
        normalized = " ".join(chunk.split())
        if heading_pattern.match(normalized) and len(normalized) <= 28:
            if buffer:
                sections.append({"section": current_title, "content": _clean_text("\n\n".join(buffer))})
                buffer = []
            current_title = normalized
        else:
            buffer.append(chunk)
    if buffer:
        sections.append({"section": current_title, "content": _clean_text("\n\n".join(buffer))})
    return [section for section in sections if section["content"]]


def _read_docx_text(path: Path) -> str:
    paragraphs: list[str] = []
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with zipfile.ZipFile(path) as package:
            xml = package.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise AppError(
            "invalid_document",
            f"DOCX 文档无法解析：{path.name}",
            "document_parser",
            status_code=400,
        ) from exc

    root = ElementTree.fromstring(xml)
    for paragraph in root.findall(".//w:p", ns):
        pieces = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        text = "".join(pieces).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise AppError(
            "pdf_parser_unavailable",
            "当前环境未安装 pypdf，暂时无法导入 PDF。可先放入 Markdown/TXT/DOCX，或安装 pypdf。",
            "document_parser",
            status_code=501,
        ) from exc
    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)


def _read_html_text(path: Path) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise AppError(
            "html_parser_unavailable",
            "当前环境未安装 beautifulsoup4，暂时无法解析 HTML。",
            "document_parser",
            status_code=501,
        ) from exc
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    for selector in [
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "aside",
        ".cookie",
        ".cookies",
        ".breadcrumb",
        ".breadcrumbs",
        ".related",
        ".menu",
        ".navigation",
    ]:
        for node in soup.select(selector):
            node.decompose()
    pieces: list[str] = []
    title = soup.find("title")
    if title and title.get_text(strip=True):
        pieces.append(title.get_text(" ", strip=True))
    for node in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        text = node.get_text(" ", strip=True)
        if text:
            pieces.append(text)
    return "\n\n".join(pieces)


def _parse_json_document(path: Path, metadata: dict[str, Any] | None = None) -> ParsedDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    fallback_title = str((metadata or {}).get("title") or path.stem)

    if isinstance(data, list):
        sections = []
        for index, item in enumerate(data):
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or ""
                title = item.get("section") or item.get("title") or f"{fallback_title}-{index + 1}"
            else:
                content = str(item)
                title = f"{fallback_title}-{index + 1}"
            if str(content).strip():
                sections.append({"section": str(title), "content": _clean_text(str(content))})
        raw_text = "\n\n".join(section["content"] for section in sections)
        return ParsedDocument(title=fallback_title, sections=sections, raw_text=raw_text)

    if not isinstance(data, dict):
        text = _clean_text(str(data))
        return ParsedDocument(title=fallback_title, sections=[{"section": fallback_title, "content": text}], raw_text=text)

    title = str(data.get("title") or fallback_title)
    sections: list[dict[str, str]] = []
    raw_parts: list[str] = []
    raw_sections = data.get("sections")
    if isinstance(raw_sections, list):
        for index, item in enumerate(raw_sections):
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or ""
                section_title = item.get("section") or item.get("title") or f"{title}-{index + 1}"
            else:
                content = str(item)
                section_title = f"{title}-{index + 1}"
            cleaned = _clean_text(str(content))
            if cleaned:
                sections.append({"section": str(section_title), "content": cleaned})
                raw_parts.append(cleaned)

    content = data.get("content") or data.get("text") or ""
    cleaned_content = _clean_text(str(content))
    if cleaned_content:
        sections.insert(0, {"section": title, "content": cleaned_content})
        raw_parts.insert(0, cleaned_content)

    raw_text = "\n\n".join(raw_parts)
    return ParsedDocument(title=title, sections=sections, raw_text=raw_text)


def _parse_jsonl_document(path: Path, metadata: dict[str, Any] | None = None) -> ParsedDocument:
    fallback_title = str((metadata or {}).get("title") or path.stem)
    sections: list[dict[str, str]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            item = {"content": line}
        if isinstance(item, dict):
            content = item.get("content") or item.get("text") or ""
            title = item.get("section") or item.get("title") or f"{fallback_title}-{index + 1}"
        else:
            content = str(item)
            title = f"{fallback_title}-{index + 1}"
        cleaned = _clean_text(str(content))
        if cleaned:
            sections.append({"section": str(title), "content": cleaned})
    raw_text = "\n\n".join(section["content"] for section in sections)
    return ParsedDocument(title=fallback_title, sections=sections, raw_text=raw_text)


def parse_document(path: Path, metadata: dict[str, Any] | None = None) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_KNOWLEDGE_EXTENSIONS:
        raise AppError(
            "unsupported_knowledge_file",
            f"不支持的知识文档类型：{suffix}",
            "document_parser",
            status_code=400,
        )

    if suffix == ".json":
        parsed = _parse_json_document(path, metadata)
        if not parsed.sections and parsed.raw_text:
            parsed.sections.append({"section": parsed.title, "content": parsed.raw_text})
        return parsed
    if suffix == ".jsonl":
        parsed = _parse_jsonl_document(path, metadata)
        if not parsed.sections and parsed.raw_text:
            parsed.sections.append({"section": parsed.title, "content": parsed.raw_text})
        return parsed

    if suffix == ".md":
        text = path.read_text(encoding="utf-8")
    elif suffix == ".txt":
        text = path.read_text(encoding="utf-8")
    elif suffix in {".html", ".htm"}:
        text = _read_html_text(path)
    elif suffix == ".docx":
        text = _read_docx_text(path)
    else:
        text = _read_pdf_text(path)

    text = _clean_text(text)
    title = str((metadata or {}).get("title") or path.stem)
    if suffix == ".md":
        sections = _sections_from_markdown(text, title)
    elif suffix in {".html", ".htm"}:
        sections = _sections_from_plain_text(text, title)
    else:
        sections = _sections_from_plain_text(text, title)
    if not sections and text:
        sections = [{"section": title, "content": text}]
    return ParsedDocument(title=title, sections=sections, raw_text=text)
