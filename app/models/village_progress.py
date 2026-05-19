from datetime import datetime

from app.extensions import db


class VillageProgress(db.Model):
    __tablename__ = "village_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    village_number = db.Column(db.Integer, nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False, default=1)
    last_studied_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    study_count = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "village_number", name="uix_user_village_progress"),
        db.Index("ix_village_progress_user_last", "user_id", "last_studied_at"),
    )

    def __repr__(self):
        return (
            f"<VillageProgress user_id={self.user_id} "
            f"village={self.village_number} lesson={self.lesson_number}>"
        )
