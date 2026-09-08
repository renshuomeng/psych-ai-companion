import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from config import get_settings
from services.video_service import analyze_video_file
from schemas.errors import AppError


async def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_ark_video.py path/to/video.mp4")
        return 2
    if not get_settings().ark_configured:
        print("ARK_API_KEY is not configured.")
        return 2
    try:
        print(await analyze_video_file(Path(sys.argv[1]), "manual-test"))
    except AppError as exc:
        print(exc.detail.model_dump())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
