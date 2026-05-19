# app/routes/main.py
from flask import render_template
from flask_login import current_user, login_required

from app.extensions import db
from app.models.chapter import Chapter
from app.models.story import Story
from app.models.story_progress import StoryProgress
from app.models.village_certification import VillageCertification
from app.models.village_progress import VillageProgress
from app.routes import main_bp


def get_latest_story_learning(user_id):
    try:
        progress = (
            StoryProgress.query.filter_by(user_id=user_id)
            .order_by(StoryProgress.last_studied_at.desc())
            .first()
        )
        if not progress:
            return None

        story = Story.query.get(progress.story_id)
        if not story:
            return None

        chapter = Chapter.query.get(story.chapter_id)
        if not chapter:
            return None

        return {
            "story": story,
            "chapter": chapter,
        }
    except Exception as exc:
        print(f"Story 대시보드 진도 조회 오류: {exc}")
        return None


def get_latest_village_learning(user_id):
    try:
        VillageProgress.__table__.create(bind=db.engine, checkfirst=True)
        return (
            VillageProgress.query.filter_by(user_id=user_id)
            .order_by(VillageProgress.last_studied_at.desc())
            .first()
        )
    except Exception as exc:
        print(f"Village 대시보드 진도 조회 오류: {exc}")
        return None


@main_bp.route("/")
@login_required
def index():
    village_latest = None
    story_latest_learning = get_latest_story_learning(current_user.id)
    village_latest_learning = get_latest_village_learning(current_user.id)

    try:
        village_latest = (
            VillageCertification.query.filter_by(user_id=current_user.id)
            .order_by(VillageCertification.exam_date.desc())
            .first()
        )
    except Exception as exc:
        print(f"Village 대시보드 조회 오류: {exc}")

    return render_template(
        "index.html",
        village_latest=village_latest,
        story_latest_learning=story_latest_learning,
        village_latest_learning=village_latest_learning,
    )
