from pathlib import Path

from services.storage_service import ALLOWED_EXTENSIONS


def test_allowed_file_types_include_browser_formats():
    assert ".webm" in ALLOWED_EXTENSIONS["audio"]
    assert ".webm" in ALLOWED_EXTENSIONS["video"]
    assert ".webp" in ALLOWED_EXTENSIONS["image"]


def test_user_filename_is_reduced_to_name_only():
    unsafe = Path("../secret/evil.jpg").name
    assert unsafe == "evil.jpg"
