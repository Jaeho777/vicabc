import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def get_database_uri():
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("SQLALCHEMY_DATABASE_URI")
        or f"sqlite:///{BASE_DIR / 'app.db'}"
    )


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "change-me-in-production"
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    NOTICE_UPLOAD_DIR = os.environ.get("NOTICE_UPLOAD_DIR")
    NOTICE_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
    NOTICE_PREVIEW_ENABLED = os.environ.get("NOTICE_PREVIEW_ENABLED", "1") == "1"
    NOTICE_PREVIEW_DIR = os.environ.get("NOTICE_PREVIEW_DIR")
    NOTICE_PREVIEW_WORK_ROOT = "/var/lib/vicabc-preview/work"
    NOTICE_PREVIEW_RENDERER = "/opt/vicabc-preview/render_notice_preview.py"
    NOTICE_PREVIEW_USER = "vicpreview"
    NOTICE_PREVIEW_TIMEOUT_SECONDS = 75
    NOTICE_PREVIEW_MAX_PAGES = 100
    NOTICE_PREVIEW_MAX_BYTES = 200 * 1024 * 1024
    NOTICE_PREVIEW_RETRY_SECONDS = 60
