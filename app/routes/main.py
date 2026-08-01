# app/routes/main.py
from datetime import datetime, timedelta

from flask import render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models.chapter import Chapter
from app.models.story import Story
from app.models.story_progress import StoryProgress
from app.models.user import User
from app.models.user_progress import UserProgress
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


def get_weekly_ranking(user_id):
    """Build a leaderboard from real weekly study records without storing fake points."""
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    scores = {}

    def add_scores(query):
        for ranked_user_id, score in query:
            scores[ranked_user_id] = scores.get(ranked_user_id, 0) + int(score or 0)

    try:
        add_scores(
            db.session.query(
                UserProgress.user_id,
                func.coalesce(func.sum(UserProgress.total_score), 0)
                + (func.coalesce(func.sum(UserProgress.study_count), 0) * 10),
            )
            .filter(UserProgress.last_studied_at >= week_start)
            .group_by(UserProgress.user_id)
            .all()
        )
        add_scores(
            db.session.query(
                StoryProgress.user_id,
                func.coalesce(func.sum(StoryProgress.total_score), 0)
                + (func.coalesce(func.sum(StoryProgress.study_count), 0) * 10),
            )
            .filter(StoryProgress.last_studied_at >= week_start)
            .group_by(StoryProgress.user_id)
            .all()
        )
        add_scores(
            db.session.query(
                VillageProgress.user_id,
                func.coalesce(func.sum(VillageProgress.study_count), 0) * 10,
            )
            .filter(VillageProgress.last_studied_at >= week_start)
            .group_by(VillageProgress.user_id)
            .all()
        )
    except Exception as exc:
        print(f"주간 랭킹 조회 오류: {exc}")
        return []

    if user_id not in scores:
        scores[user_id] = 0

    users = User.query.filter(User.id.in_(scores)).all()
    users_by_id = {user.id: user for user in users}
    ranked_users = sorted(
        (
            (ranked_user_id, score)
            for ranked_user_id, score in scores.items()
            if ranked_user_id in users_by_id
        ),
        key=lambda item: (-item[1], users_by_id[item[0]].full_name),
    )[:5]

    return [
        {
            "rank": index,
            "name": users_by_id[ranked_user_id].full_name,
            "score": score,
            "is_current_user": ranked_user_id == user_id,
        }
        for index, (ranked_user_id, score) in enumerate(ranked_users, start=1)
    ]


@main_bp.route("/")
@login_required
def index():
    village_latest = None
    story_latest_learning = get_latest_story_learning(current_user.id)
    village_latest_learning = get_latest_village_learning(current_user.id)
    weekly_ranking = get_weekly_ranking(current_user.id)

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
        today_label=datetime.now().strftime("%Y년 %m월 %d일"),
        village_latest=village_latest,
        story_latest_learning=story_latest_learning,
        village_latest_learning=village_latest_learning,
        weekly_ranking=weekly_ranking,
    )
