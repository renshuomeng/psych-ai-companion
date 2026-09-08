import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from config import get_settings
from services.speech_service import transcribe_audio
from schemas.errors import AppError


async def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_doubao_asr.py path/to/audio.wav")
        return 2
    if not get_settings().speech_configured:
        print("Doubao speech credentials are not configured.")
        return 2
    try:
        print(await transcribe_audio(Path(sys.argv[1]), "manual-test"))
    except AppError as exc:
        print(exc.detail.model_dump())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
