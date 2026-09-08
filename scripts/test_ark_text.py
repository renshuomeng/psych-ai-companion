import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from config import get_settings
from services.ark_client import generate_text
from schemas.errors import AppError


async def main() -> int:
    if not get_settings().ark_configured:
        print("ARK_API_KEY is not configured. Fill backend .env or project .env first.")
        return 2
    try:
        result = await generate_text(
            "你是安全型心理陪伴助手，不做诊断。",
            "请用一句话回应：最近论文压力很大。",
        )
    except AppError as exc:
        print(exc.detail.model_dump())
        return 1
    print({"provider": result.provider, "model": result.model, "request_id": result.request_id})
    print(result.text[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
