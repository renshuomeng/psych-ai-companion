import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATTERNS = [
    ".env",
    "backend/database/*.sqlite",
    "backend/database/*.db",
    "backend/data/uploads/**",
    "backend/data/chroma_db/**",
    "backend/data/knowledge_base/indexes/**",
    "evaluation/results/**",
    "competition_results/**",
    "logs/**",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="List private/generated files that should not be committed.")
    parser.parse_args()
    findings = []
    for pattern in PRIVATE_PATTERNS:
        findings.extend(path for path in ROOT.glob(pattern) if path.exists())
    if findings:
        print("Private/generated paths present locally; keep them ignored:")
        for path in findings[:200]:
            print(f"- {path.relative_to(ROOT)}")
    else:
        print("No private/generated files found by configured patterns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
