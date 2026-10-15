"""Metadata for private notice attachments; binary files stay outside static/."""

from datetime import datetime

from app.extensions import db


class NoticeAttachment(db.Model):
    __tablename__ = "notice_attachments"

    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(
        db.Integer, db.ForeignKey("notices.id"), nullable=False, unique=True
    )
    original_name = db.Column(db.String(200), nullable=False)
    storage_name = db.Column(db.String(50), nullable=False, unique=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    notice = db.relationship("Notice", back_populates="attachment")
