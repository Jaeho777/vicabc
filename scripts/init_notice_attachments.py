"""Add the attachment metadata table; existing notices and users are preserved.

Run with the same DATABASE_URL/SQLALCHEMY_DATABASE_URI as the application:
    python scripts/init_notice_attachments.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask

from app.config import Config
from app.extensions import db
from app.models.notice import Notice
from app.models.notice_attachment import NoticeAttachment


def initialize_attachment_table():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    with app.app_context():
        Notice.__table__.create(bind=db.engine, checkfirst=True)
        NoticeAttachment.__table__.create(bind=db.engine, checkfirst=True)
    return app


if __name__ == "__main__":
    initialize_attachment_table()
    print("Notice attachment table is ready.")
