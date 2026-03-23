from datetime import datetime

from app.extensions import db


class VillageCertification(db.Model):
    __tablename__ = "village_certifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic = db.Column(db.String(120), default="daily conversation", nullable=False)
    level_label = db.Column(db.String(50), nullable=False)
    passed = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=0)
    turn_count = db.Column(db.Integer, default=0)
    transcript = db.Column(db.Text, default="")
    feedback = db.Column(db.Text, default="")
    exam_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref("village_certifications", lazy="dynamic"),
    )

    def __repr__(self):
        return (
            f"<VillageCertification user_id={self.user_id} "
            f"score={self.score} level={self.level_label}>"
        )
