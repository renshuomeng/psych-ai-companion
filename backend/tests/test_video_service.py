from services.media_service import ffmpeg_status
from services.media_service import ensure_ffmpeg, ensure_ffprobe


def test_ffmpeg_status_shape():
    status = ffmpeg_status()
    assert status["ffmpeg"] in {"ok", "missing"}
    assert status["ffprobe"] in {"ok", "missing"}


def test_configured_ffmpeg_paths_are_usable():
    status = ffmpeg_status()
    if status["ffmpeg"] == "ok":
        assert ensure_ffmpeg()
    if status["ffprobe"] == "ok":
        assert ensure_ffprobe()
