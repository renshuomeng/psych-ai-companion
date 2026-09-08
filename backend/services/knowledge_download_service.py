from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from schemas.errors import AppError
from services.knowledge_source_registry import (
    KnowledgeSourceEntry,
    KnowledgeSourceRegistry,
    domain_allowed,
    ensure_registry_directories,
)


USER_AGENT = "CARE-Psy-RAG-V1/1.0 (+local research prototype)"


@dataclass
class DownloadedFile:
    source_id: str
    path: Path
    downloaded_url: str
    final_url: str
    http_status: int
    mime_type: str
    sha256: str
    file_size: int
    status: str = "success"
    duplicate_of: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_filename(value: str, fallback: str = "download") -> str:
    value = re.sub(r"[^\w.\-]+", "_", value.strip(), flags=re.UNICODE).strip("._")
    return value[:90] or fallback


def _extension_from_url_or_type(url: str, mime_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension((mime_type or "").split(";")[0].strip())
    return guessed or ".bin"


def _looks_like_allowed_asset(
    href: str,
    text: str,
    download_config: dict[str, Any],
) -> bool:
    patterns = [str(item).lower() for item in download_config.get("include_link_text_patterns") or []]
    allowed_extensions = [str(item).lower() for item in download_config.get("allowed_extensions") or []]
    preferred_mime = [str(item).lower() for item in download_config.get("preferred_mime_types") or []]
    combined = f"{href} {text}".lower()
    if patterns and not any(pattern.lower() in combined for pattern in patterns):
        return False
    if allowed_extensions and not any(urlparse(href).path.lower().endswith(ext) for ext in allowed_extensions):
        return False
    if preferred_mime and not allowed_extensions:
        if any("pdf" in mime for mime in preferred_mime) and ".pdf" in combined:
            return True
        if any("html" in mime for mime in preferred_mime):
            return True
    if not patterns and not allowed_extensions:
        return "download" in combined or ".pdf" in combined or ".zip" in combined
    return True


def safe_extract_zip(zip_path: Path, destination: Path) -> list[Path]:
    extracted: list[Path] = []
    destination = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_name = member.filename.replace("\\", "/")
            if member_name.startswith("/") or ".." in Path(member_name).parts:
                raise AppError(
                    "unsafe_zip_member",
                    f"Unsafe ZIP member path rejected: {member.filename}",
                    "knowledge_download",
                    status_code=400,
                )
            target = (destination / member_name).resolve()
            if destination not in target.parents and target != destination:
                raise AppError(
                    "unsafe_zip_member",
                    f"ZIP member escapes target directory: {member.filename}",
                    "knowledge_download",
                    status_code=400,
                )
        archive.extractall(destination)
    for path in destination.rglob("*"):
        if path.is_file():
            extracted.append(path)
    return extracted


class KnowledgeDownloader:
    def __init__(self, registry: KnowledgeSourceRegistry) -> None:
        self.registry = registry
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.min_delay = float(registry.build_policy.get("minimum_delay_seconds_per_domain", 1.0))
        self.timeout = int(registry.build_policy.get("request_timeout_seconds", 30))
        self._last_request_at: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._seen_sha: dict[str, str] = {}

    def _wait_for_domain(self, url: str) -> None:
        domain = urlparse(url).netloc.lower()
        last = self._last_request_at.get(domain, 0.0)
        wait = self.min_delay - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at[domain] = time.monotonic()

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in self._robots:
            return self._robots[base]
        parser = RobotFileParser()
        robots_url = urljoin(base, "/robots.txt")
        parser.set_url(robots_url)
        try:
            self._wait_for_domain(robots_url)
            response = self.session.get(robots_url, timeout=min(self.timeout, 10), allow_redirects=True)
            if response.status_code >= 400:
                self._robots[base] = None
                return None
            parser.parse(response.text.splitlines())
        except Exception:
            self._robots[base] = None
            return None
        self._robots[base] = parser
        return parser

    def _check_can_fetch(self, url: str) -> None:
        parser = self._robots_for(url)
        if parser is not None and not parser.can_fetch(USER_AGENT, url):
            raise AppError(
                "robots_disallowed",
                f"robots.txt disallows fetching URL: {url}",
                "knowledge_download",
                status_code=403,
            )

    def _get(self, url: str, source: KnowledgeSourceEntry) -> requests.Response:
        allowed_domains = [str(item) for item in source.download.get("allowed_domains") or []]
        if not domain_allowed(url, allowed_domains):
            raise AppError(
                "download_domain_not_allowed",
                f"URL is outside allowed_domains for {source.id}: {url}",
                "knowledge_download",
                status_code=400,
            )
        self._check_can_fetch(url)
        self._wait_for_domain(url)
        response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        if not domain_allowed(response.url, allowed_domains):
            raise AppError(
                "redirect_domain_not_allowed",
                f"Redirect target is outside allowed_domains for {source.id}: {response.url}",
                "knowledge_download",
                status_code=400,
            )
        response.raise_for_status()
        return response

    def _write_response(
        self,
        source: KnowledgeSourceEntry,
        response: requests.Response,
        target_dir: Path,
        name_hint: str,
        downloaded_url: str,
    ) -> DownloadedFile:
        mime_type = response.headers.get("content-type", "").split(";")[0].strip()
        extension = _extension_from_url_or_type(response.url, mime_type)
        file_name = safe_filename(name_hint, source.id)
        if not file_name.lower().endswith(extension.lower()):
            file_name = f"{file_name}{extension}"
        target = target_dir / file_name
        counter = 2
        while target.exists():
            target = target_dir / f"{Path(file_name).stem}_{counter}{Path(file_name).suffix}"
            counter += 1
        target.write_bytes(response.content)
        digest = sha256_file(target)
        duplicate_of = self._seen_sha.get(digest, "")
        if not duplicate_of:
            self._seen_sha[digest] = str(target)
        return DownloadedFile(
            source_id=source.id,
            path=target,
            downloaded_url=downloaded_url,
            final_url=response.url,
            http_status=response.status_code,
            mime_type=mime_type or mimetypes.guess_type(target.name)[0] or "",
            sha256=digest,
            file_size=target.stat().st_size,
            status="duplicate" if duplicate_of else "success",
            duplicate_of=duplicate_of,
        )

    def _html_links(self, html: str, base_url: str) -> list[tuple[str, str]]:
        try:
            from bs4 import BeautifulSoup
        except Exception as exc:
            raise AppError(
                "html_parser_unavailable",
                "beautifulsoup4 is required to discover official download links",
                "knowledge_download",
                status_code=503,
            ) from exc
        soup = BeautifulSoup(html, "html.parser")
        links: list[tuple[str, str]] = []
        for anchor in soup.find_all("a"):
            href = anchor.get("href")
            if not href:
                continue
            text = " ".join(anchor.get_text(" ", strip=True).split())
            links.append((urljoin(base_url, str(href)), text))
        return links

    def download_source(self, source: KnowledgeSourceEntry) -> tuple[list[DownloadedFile], list[dict[str, Any]]]:
        source_dir = self.registry.paths["raw_auto"] / source.id
        source_dir.mkdir(parents=True, exist_ok=True)
        errors: list[dict[str, Any]] = []
        files: list[DownloadedFile] = []
        try:
            page_response = self._get(source.official_page_url, source)
            page_file = self._write_response(
                source,
                page_response,
                source_dir,
                "source",
                source.official_page_url,
            )
            if page_file.path.suffix.lower() not in {".html", ".htm"} and "html" in page_file.mime_type:
                renamed = page_file.path.with_suffix(".html")
                page_file.path.rename(renamed)
                page_file.path = renamed
            files.append(page_file)

            mode = str(source.download.get("mode") or "html_page")
            if mode == "html_page":
                return files, errors

            links = self._html_links(page_response.text, page_response.url)
            max_assets = int(source.download.get("max_assets") or 1)
            selected: list[tuple[str, str]] = []
            for href, text in links:
                if not domain_allowed(href, [str(item) for item in source.download.get("allowed_domains") or []]):
                    continue
                if _looks_like_allowed_asset(href, text, source.download):
                    selected.append((href, text))
                if len(selected) >= max_assets:
                    break
            if mode == "follow_official_download_link" and not selected:
                selected = [
                    (href, text)
                    for href, text in links
                    if domain_allowed(href, [str(item) for item in source.download.get("allowed_domains") or []])
                    and (".pdf" in href.lower() or "pdf" in text.lower() or "download" in text.lower())
                ][:max_assets]

            for href, text in selected:
                try:
                    response = self._get(href, source)
                    asset = self._write_response(source, response, source_dir, text or Path(urlparse(href).path).name, href)
                    files.append(asset)
                    if asset.path.suffix.lower() == ".zip":
                        try:
                            safe_extract_zip(asset.path, source_dir)
                        except AppError as exc:
                            errors.append({"source_id": source.id, "url": href, "code": exc.detail.code, "message": exc.detail.message})
                except Exception as exc:
                    errors.append(
                        {
                            "source_id": source.id,
                            "url": href,
                            "code": getattr(getattr(exc, "detail", None), "code", "download_failed"),
                            "message": str(exc),
                        }
                    )
        except Exception as exc:
            errors.append(
                {
                    "source_id": source.id,
                    "url": source.official_page_url,
                    "code": getattr(getattr(exc, "detail", None), "code", "download_failed"),
                    "message": str(exc),
                }
            )
        return files, errors


def _manifest_record(source: KnowledgeSourceEntry, item: DownloadedFile) -> dict[str, Any]:
    return {
        "source_id": source.id,
        "organization": source.organization,
        "title": source.title,
        "official_page_url": source.official_page_url,
        "downloaded_url": item.downloaded_url,
        "final_url": item.final_url,
        "http_status": item.http_status,
        "mime_type": item.mime_type,
        "file_name": item.path.name,
        "file_path": item.path.as_posix(),
        "file_size": item.file_size,
        "sha256": item.sha256,
        "downloaded_at": utc_now_iso(),
        "status": item.status,
        "duplicate_of": item.duplicate_of,
        "target_collection": source.target_collection,
    }


def download_registry_sources(registry: KnowledgeSourceRegistry) -> dict[str, Any]:
    ensure_registry_directories(registry)
    reports_dir = registry.paths["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    downloader = KnowledgeDownloader(registry)
    manifest_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    by_source: dict[str, dict[str, Any]] = {}
    current_source_ids = {source.id for source in registry.auto_download_sources}
    for source in registry.auto_download_sources:
        print(f"downloading: {source.id}", flush=True)
        files, source_errors = downloader.download_source(source)
        by_source[source.id] = {
            "source_id": source.id,
            "title": source.title,
            "target_collection": source.target_collection,
            "files": len(files),
            "errors": len(source_errors),
            "status": "failed" if not files else "partial" if source_errors else "success",
        }
        manifest_records.extend(_manifest_record(source, item) for item in files)
        errors.extend(source_errors)

    manifest_path = reports_dir / "download_manifest.jsonl"
    existing_manifest: list[dict[str, Any]] = []
    if manifest_path.exists():
        existing_manifest = [
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    preserved_manifest = [
        record for record in existing_manifest if str(record.get("source_id") or "") not in current_source_ids
    ]
    combined_manifest = [*preserved_manifest, *manifest_records]
    manifest_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in combined_manifest) + ("\n" if combined_manifest else ""),
        encoding="utf-8",
    )
    summary = {
        "registry_name": registry.registry_name,
        "total_sources": len(registry.sources),
        "auto_download_sources": len(registry.auto_download_sources),
        "successful_sources": sum(1 for item in by_source.values() if item["status"] == "success"),
        "partial_sources": sum(1 for item in by_source.values() if item["status"] == "partial"),
        "failed_sources": sum(1 for item in by_source.values() if item["status"] == "failed"),
        "files_downloaded": len([item for item in manifest_records if item["status"] == "success"]),
        "duplicates": len([item for item in manifest_records if item["status"] == "duplicate"]),
        "bytes_downloaded": sum(int(item.get("file_size") or 0) for item in manifest_records),
        "manifest_total_records": len(combined_manifest),
        "by_source": list(by_source.values()),
        "errors": errors,
        "manifest_path": manifest_path.as_posix(),
        "created_at": utc_now_iso(),
    }
    (reports_dir / "download_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
