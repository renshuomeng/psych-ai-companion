import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "node_modules",
    "dist",
    "logs",
    "data",
    "uploads",
    "__pycache__",
    "work",
}
SECRET_PATTERNS = [
    re.compile(r"ARK_API_KEY\s*=\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"VOLC_SPEECH_(API_KEY|ACCESS_KEY)\s*=\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(cloudflare|cloudflared).{0,40}(token|secret)\s*[:=]\s*[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def should_skip(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    if parts & EXCLUDED_DIRS:
        return True
    if path.name == ".env":
        return True
    if path.name == ".env.example":
        return True
    if path.name.upper() == "README.MD":
        return True
    if path.name == "check_secrets.py":
        return True
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".mp4", ".sqlite", ".db"}:
        return True
    return False


def main() -> int:
    findings: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            findings.append(path.relative_to(ROOT))

    if findings:
        print("Potential secret patterns found:")
        for path in findings:
            print(f"- {path}")
        return 1
    print("No obvious secret patterns found outside ignored local files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
