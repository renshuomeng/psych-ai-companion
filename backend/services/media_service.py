import json
import os
import shutil
import subprocess
from pathlib import Path

from config import get_settings
from schemas.errors import AppError


def _candidate_names(executable_name: str) -> list[str]:
    if os.name == "nt" and not executable_name.endswith(".exe"):
        return [f"{executable_name}.exe", executable_name]
    return [executable_name]


def _configured_executable(configured_path: Path | None, executable_name: str) -> str | None:
    if not configured_path:
        return None
    candidate = Path(configured_path).expanduser()
    if candidate.is_dir():
        for name in _candidate_names(executable_name):
            nested = candidate / name
            if nested.exists() and nested.is_file():
                return str(nested)
        return None
    if candidate.exists() and candidate.is_file():
        return str(candidate)
    return None


def _resolve_executable(executable_name: str, configured_path: Path | None) -> str | None:
    configured = _configured_executable(configured_path, executable_name)
    if configured:
        return configured
    for name in _candidate_names(executable_name):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def ffmpeg_status() -> dict[str, str]:
    settings = get_settings()
    return {
        "ffmpeg": "ok" if _resolve_executable("ffmpeg", settings.ffmpeg_path) else "missing",
        "ffprobe": "ok" if _resolve_executable("ffprobe", settings.ffprobe_path) else "missing",
    }


def ensure_ffprobe(stage: str = "media_probe") -> str:
    executable = _resolve_executable("ffprobe", get_settings().ffprobe_path)
    if not executable:
        raise AppError(
            code="ffmpeg_not_found",
            message="未检测到 ffprobe，无法验证音频或视频文件。请先安装 ffmpeg。",
            stage=stage,
            retryable=False,
            status_code=503,
        )
    return executable


def ensure_ffmpeg(stage: str = "media_conversion") -> str:
    executable = _resolve_executable("ffmpeg", get_settings().ffmpeg_path)
    if not executable:
        raise AppError(
            code="ffmpeg_not_found",
            message="未检测到 ffmpeg，无法进行音视频转换或提取音轨。",
            stage=stage,
            retryable=False,
            status_code=503,
        )
    return executable


def probe_media(path: Path, stage: str = "media_probe") -> dict:
    ffprobe = ensure_ffprobe(stage)
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise AppError(
            code="invalid_media",
            message="媒体文件无法被 ffprobe 解析，可能已损坏或格式不受支持。",
            stage=stage,
            retryable=False,
            status_code=400,
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AppError(
            code="invalid_media",
            message="媒体探测结果解析失败。",
            stage=stage,
            retryable=False,
            status_code=400,
        ) from exc

    return payload


def get_duration_seconds(path: Path, stage: str = "media_probe") -> float | None:
    payload = probe_media(path, stage=stage)
    duration = payload.get("format", {}).get("duration")
    if duration is None:
        return None
    try:
        return float(duration)
    except (TypeError, ValueError):
        return None


def extract_audio_to_wav(video_path: Path, output_path: Path) -> Path:
    ffmpeg = ensure_ffmpeg("video_audio_extract")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0 or not output_path.exists():
        raise AppError(
            code="media_conversion_failed",
            message="视频音轨提取失败，请检查视频格式或 ffmpeg 安装。",
            stage="video_audio_extract",
            retryable=False,
            status_code=400,
        )
    return output_path


def extract_video_frame(video_path: Path, output_path: Path, at_seconds: float = 1.0) -> Path:
    ffmpeg = ensure_ffmpeg("video_frame_extract")
    command = [
        ffmpeg,
        "-y",
        "-ss",
        str(max(at_seconds, 0)),
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0 or not output_path.exists():
        raise AppError(
            code="video_frame_extract_failed",
            message="视频关键帧提取失败，请检查视频格式或 ffmpeg 安装。",
            stage="video_frame_extract",
            retryable=False,
            status_code=400,
        )
    return output_path
