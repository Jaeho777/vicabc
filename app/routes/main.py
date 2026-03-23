# app/routes/main.py
from flask import render_template
from flask_login import current_user, login_required

from app.extensions import db
from app.models.village_certification import VillageCertification
from app.routes import main_bp


@main_bp.route("/")
@login_required
def index():
    village_latest = None

    try:
        village_latest = (
            VillageCertification.query.filter_by(user_id=current_user.id)
            .order_by(VillageCertification.exam_date.desc())
            .first()
        )
    except Exception as exc:
        print(f"Village 대시보드 조회 오류: {exc}")

    return render_template("index.html", village_latest=village_latest)
